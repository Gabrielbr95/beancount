"""
B3 Importer for Beangulp.

Consumes XLSX reports containing "Negociação" and/or "Movimentação" sheets.
Generates Beancount directives for trades, dividends, corporate actions, and more.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import List, Optional, Dict, Any

import openpyxl
from beancount.core import data, amount, inventory
from beancount.core.position import CostSpec
import beangulp

# Mapping of institution names to short codes
INST_MAP = {
    "xp investimentos cctvm s/a": "XP",
    "modal dtvm ltda": "Modal",
    "clear corretora": "Clear",
    "inter distribuidora": "Inter",
    "banco do brasil s/a": "BB",
    "itaú": "Inter",  # fallback or specific mapping
}

def normalize_inst(inst: str) -> str:
    inst_lower = inst.lower().strip()
    for key, val in INST_MAP.items():
        if key in inst_lower:
            return val
    # Fallback: take first word, title case
    return inst.split()[0].title() if inst else "Unknown"

def extract_ticker(produto: str) -> str:
    if " - " in produto:
        ticker = produto.split(" - ")[0].strip()
    else:
        ticker = produto.strip()
    # Remove trailing 'F' for fractional market trades
    if ticker.endswith("F"):
        ticker = ticker[:-1]
    return ticker

def normalize_fixed_income_ticker(produto: str) -> str:
    # Uppercase, remove accents, replace spaces with _, remove special chars
    text = unicodedata.normalize("NFKD", produto).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^A-Z0-9\s]", "", text.upper())
    return text.replace(" ", "_")

def parse_date(value) -> Optional[date]:
    if value is None:
        return None

    # Already a date
    if isinstance(value, date) and not isinstance(value, datetime):
        return value

    # Datetime -> date
    if isinstance(value, datetime):
        return value.date()

    # String parsing
    value = str(value).strip()
    if not value or value == "-":
        return None

    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d/%m/%y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass

    return None

def parse_decimal(val: Any) -> Optional[Decimal]:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return Decimal(str(val))
    val_str = str(val).strip()
    if val_str == "-" or val_str == "":
        return None
    # Handle Brazilian format: 1.000,00 -> remove dots, replace comma with dot
    val_str = val_str.replace(".", "").replace(",", ".")
    # Remove currency symbols or spaces
    val_str = re.sub(r"[^\d.\-]", "", val_str)
    if not val_str or val_str == "-" or val_str == "":
        return None
    try:
        return Decimal(val_str)
    except InvalidOperation:
        return None

def is_fii_ticker(ticker: str) -> bool:
    return bool(re.match(r"^[A-Z]{4}\d{2}$", ticker))

class B3Importer(beangulp.Importer):
    def __init__(self, account_root: str = "Assets:Investment"):
        self.account_root = account_root.rstrip(":")

    def identify(self, filepath: str) -> bool:
        if not filepath.lower().endswith(".xlsx"):
            return False
        try:
            wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
            # Check if it has expected sheets
            has_sheet = any("Movimentação" in sh or "Negociação" in sh for sh in wb.sheetnames)
            wb.close()
            print ("true")
            return has_sheet
        except Exception as e:
            raise e
            return False

    def name(self) -> str:
        return "B3 Importer"

    def account(self, filepath: str) -> str:
        return f"{self.account_root}:B3"

    def date(self, filepath: str) -> Optional[datetime.date]:
        try:
            wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
            for sheet_name in wb.sheetnames:
                if "Movimentação" in sheet_name or "Negociação" in sheet_name:
                    ws = wb[sheet_name]
                    for row in ws.iter_rows(min_row=2, max_row=50, values_only=True):
                        date_val = row[1] if "Movimentação" in sheet_name else row[0]
                        d = parse_date(date_val)
                        if d:
                            wb.close()
                            return d
            wb.close()
        except Exception:
            pass
        return None

    def filename(self, filepath: str) -> str:
        import os
        base = os.path.basename(filepath)
        d = self.date(filepath)
        if d:
            return f"{d.strftime('%Y-%m-%d')}.{base}"
        return base

    def extract(self, filepath: str, existing_entries: List[data.Directive]) -> List[data.Directive]:
        entries = []
        try:
            wb = openpyxl.load_workbook(filepath, read_only=False, data_only=True)
            
            # Process sheets
            for sheet_name in wb.sheetnames:
                if "Negociação" in sheet_name:
                    entries.extend(self._extract_negociacao(filepath, wb[sheet_name]))
                elif "Movimentação" in sheet_name:
                    entries.extend(self._extract_movimentacao(filepath, wb[sheet_name]))
            
            wb.close()
        except Exception as e:
            print(f"Error processing {filepath}: {e}")
            
        return sorted(entries, key=lambda e: (getattr(e, 'date', None), e.meta.get('lineno', 0)))

    def _new_meta(self, filepath: str, lineno: int, extra: Dict[str, str] = None) -> data.Meta:
        meta = data.new_metadata(filepath, lineno)
        if extra:
            meta.update(extra)
        return meta

    def _extract_negociacao(self, filepath: str, ws) -> List[data.Directive]:
        entries = []
        # Find header row
        headers = None
        for row_idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
            if row and any("Data do Negócio" in str(c) for c in row if c):
                headers = [str(c).strip() if c else "" for c in row]
                start_row = row_idx + 1
                break
        else:
            return entries

        if not headers:
            return entries

        header_map = {h: i for i, h in enumerate(headers)}
        
        for row_idx, row in enumerate(ws.iter_rows(min_row=start_row, values_only=True), start=start_row):
            if not row or all(c is None for c in row):
                continue
            
            date_val = row[header_map.get("Data do Negócio", 0)]
            tipo = row[header_map.get("Tipo de Movimentação", 1)]
            mercado = row[header_map.get("Mercado", 2)]
            inst_raw = row[header_map.get("Instituição", 4)]
            codigo = row[header_map.get("Código de Negociação", 5)]
            qty_val = row[header_map.get("Quantidade", 6)]
            price_val = row[header_map.get("Preço", 7)]
            valor_val = row[header_map.get("Valor", 8)]

            date = parse_date(date_val)
            if not date or not codigo:
                continue

            ticker = extract_ticker(str(codigo))
            inst = normalize_inst(str(inst_raw))
            qty = parse_decimal(qty_val)
            price = parse_decimal(price_val)
            valor = parse_decimal(valor_val)

            if qty is None or valor is None:
                continue

            meta = self._new_meta(filepath, row_idx, {
                "id": f"b3neg-{date.strftime('%Y%m%d')}-{ticker}-{row_idx}",
                "source": "b3_negociacoes",
                "asset": ticker,
                "mercado": str(mercado) if mercado else ""
            })

            cash_account = f"{self.account_root}:{inst}:Cash"
            asset_account = f"{self.account_root}:{inst}:{ticker}"
            gains_account = f"Income:Investment:{inst}:Gains"

            if tipo == "Compra":
                cost = amount.Amount(price, "BRL") if price is not None else None
                units = amount.Amount(qty, ticker)
                cash_units = amount.Amount(-abs(valor), "BRL")
                
                postings = [
                    data.Posting(asset_account, units, cost, None, None, None),
                    data.Posting(cash_account, cash_units, None, None, None, None),
                ]
                txn = data.Transaction(meta, date, "*", None, f"Compra {ticker}", data.EMPTY_SET, data.EMPTY_SET, postings)
                entries.append(txn)

            elif tipo == "Venda":
                units = amount.Amount(-abs(qty), ticker)
                cash_units = amount.Amount(abs(valor), "BRL")
                
                postings = [
                    data.Posting(cash_account, cash_units, None, None, None, None),
                    data.Posting(asset_account, units, None, None, None, None),
                    data.Posting(gains_account, None, None, None, None, None),
                ]
                txn = data.Transaction(meta, date, "*", None, f"Venda {ticker}", data.EMPTY_SET, data.EMPTY_SET, postings)
                entries.append(txn)

        return entries

    def _extract_movimentacao(self, filepath: str, ws) -> List[data.Directive]:
        entries = []
        headers = None
        for row_idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
            if row and any("Entrada/Saída" in str(c) for c in row if c):
                headers = [str(c).strip() if c else "" for c in row]
                start_row = row_idx + 1
                break
        else:
            return entries

        if not headers:
            return entries

        header_map = {h: i for i, h in enumerate(headers)}
        
        for row_idx, row in enumerate(ws.iter_rows(min_row=start_row, values_only=True), start=start_row):
            if not row or all(c is None for c in row):
                continue
            
            entrada_saida = row[header_map.get("Entrada/Saída", 0)]
            date_val = row[header_map.get("Data", 1)]
            movimentacao = row[header_map.get("Movimentação", 3)]
            produto = row[header_map.get("Produto", 4)]
            inst_raw = row[header_map.get("Instituição", 5)]
            qty_val = row[header_map.get("Quantidade", 6)]
            preco_val = row[header_map.get("Preço unitário", 7)]
            valor_val = row[header_map.get("Valor da Operação", 8)]

            date = parse_date(date_val)
            if not date or not produto:
                continue

            ticker = extract_ticker(str(produto))
            is_fii = is_fii_ticker(ticker)
            
            # Normalize fixed income tickers if not a standard stock/FII ticker
            if not re.match(r"^[A-Z]{4}\d{1,4}$", ticker) and movimentacao not in ("Atualização", "Cisão", "Incorporação"):
                ticker = normalize_fixed_income_ticker(str(produto))

            inst = normalize_inst(str(inst_raw))
            qty = parse_decimal(qty_val)
            preco = parse_decimal(preco_val)
            valor = parse_decimal(valor_val)

            entrada_saida_str = str(entrada_saida).strip().lower() if entrada_saida else ""
            mov_str = str(movimentacao).strip()

            # Ignore rules
            if mov_str in ("Atualização", "Cisão", "Incorporação", "Resgate"):
                continue
            
            # Skip if quantity and value are both missing/dash
            if qty is None and valor is None:
                continue

            meta = self._new_meta(filepath, row_idx, {
                "id": f"b3mov-{date.strftime('%Y%m%d')}-{ticker}-{row_idx}",
                "source": "b3_movimentacoes",
                "asset": ticker,
                "original_tipo": mov_str
            })

            cash_account = f"{self.account_root}:{inst}:Cash"
            asset_account = f"{self.account_root}:{inst}:{ticker}"
            
            # Warning for unmatched/resgate
            if mov_str == "Resgate":
                meta["warning"] = "ticker_migration"
                entries.append(self._skip_tx(meta, date, f"Resgate {ticker} (ignored/manual review)"))
                continue

            postings = []
            narration = f"{mov_str} {ticker}"

            empty_cost = CostSpec(None, None, None, None, None, None)

            # 1. Income events
            if mov_str in ("Dividendo",):
                meta["warning"] = "needs_review" if "Transferido" in mov_str else None
                inc_account = f"Income:Investment:{inst}:Dividend"
                if is_fii:
                    inc_account = f"Income:Investment:{inst}:Rendimento"
                if valor is not None:
                    postings = [
                        data.Posting(cash_account, amount.Amount(abs(valor), "BRL"), None, None, None, None),
                        data.Posting(inc_account, amount.Amount(-abs(valor), "BRL"), None, None, None, None),
                    ]

            elif mov_str in ("Juros Sobre Capital Próprio", "Juros Sobre Capital Próprio - Transferido"):
                if valor is not None:
                    postings = [
                        data.Posting(cash_account, amount.Amount(abs(valor), "BRL"), None, None, None, None),
                        data.Posting(f"Income:Investment:{inst}:JCP", amount.Amount(-abs(valor), "BRL"), None, None, None, None),
                    ]

            elif mov_str in ("Rendimento", "Rendimento - Transferido"):
                if valor is not None:
                    postings = [
                        data.Posting(cash_account, amount.Amount(abs(valor), "BRL"), None, None, None, None),
                        data.Posting(f"Income:Investment:{inst}:Rendimento", amount.Amount(-abs(valor), "BRL"), None, None, None, None),
                    ]

            elif mov_str in ("PAGAMENTO DE JUROS",):
                if valor is not None:
                    postings = [
                        data.Posting(cash_account, amount.Amount(abs(valor), "BRL"), None, None, None, None),
                        data.Posting(f"Income:Investment:{inst}:Interest", amount.Amount(-abs(valor), "BRL"), None, None, None, None),
                    ]

            # 2. Corporate Actions
            elif mov_str in ("Bonificação em Ativos", "Desdobro", "Grupamento"):
                if qty is not None and qty > 0:
                    postings = [
                        data.Posting(asset_account, amount.Amount(qty, ticker), empty_cost, None, None, None),
                        data.Posting("Equity:CorporateActions", None, None, None, None, None),
                    ]
                    narration = f"Corporate Action: {mov_str} {ticker}"

            elif mov_str in ("Direitos de Subscrição - Exercido", "Fração em Ativos"):
                if qty is not None:
                    postings = [
                        data.Posting(asset_account, amount.Amount(qty, ticker), empty_cost, None, None, None),
                        data.Posting("Equity:CorporateActions", None, None, None, None, None),
                    ]
                    meta["warning"] = "needs_review"

            elif mov_str in ("Leilão de Fração",):
                if qty is not None and valor is not None:
                    postings = [
                        data.Posting(cash_account, amount.Amount(abs(valor), "BRL"), None, None, None, None),
                        data.Posting(asset_account, amount.Amount(-abs(qty), ticker), None, None, None, None),
                        data.Posting(f"Income:Investment:{inst}:Gains", None, None, None, None, None),
                    ]

            # 3. Transfers
            elif "Transferência" in mov_str and "Liquidação" not in mov_str:
                # Pure custody transfer, ignore pure cash/internal moves, but log asset transfer if qty present
                if qty is not None and qty > 0:
                    # We don't know the other broker, so we just log the receipt or mark for review
                    meta["warning"] = "unmatched_transfer"
                    narration = f"Asset Transfer (Review): {ticker}"
                    postings = [
                        data.Posting(asset_account, amount.Amount(qty, ticker), None, None, None, None),
                        data.Posting("Equity:Transfers", amount.Amount(qty, ticker), None, None, None, None), # balancing
                    ]
                else:
                    continue # Ignore cash-only transfer lines

            elif "Transferência - Liquidação" in mov_str:
                if qty is not None and preco is not None and valor is not None:
                    if entrada_saida_str == "credito":
                        # Buy settled via transfer
                        postings = [
                            data.Posting(asset_account, amount.Amount(abs(qty), ticker), amount.Amount(preco, "BRL"), None, None, None),
                            data.Posting(cash_account, amount.Amount(-abs(valor), "BRL"), None, None, None, None),
                        ]
                    elif entrada_saida_str == "debito":
                        # Sell settled via transfer
                        postings = [
                            data.Posting(cash_account, amount.Amount(abs(valor), "BRL"), None, None, None, None),
                            data.Posting(asset_account, amount.Amount(-abs(qty), ticker), None, None, None, None),
                            data.Posting(f"Income:Investment:{inst}:Gains", None, None, None, None, None),
                        ]

            # 4. Fixed Income / Treasury
            elif mov_str in ("Compra", "APLICAÇÃO", "COMPRA / VENDA", "COMPRA/VENDA"):
                if qty is not None and valor is not None:
                    if entrada_saida_str == "credito":
                        # Asset in
                        postings = [
                            data.Posting(asset_account, amount.Amount(abs(qty), ticker), empty_cost, None, None, None),
                            data.Posting(cash_account, amount.Amount(-abs(valor), "BRL"), None, None, None, None),
                        ]
                    else:
                        # Asset out (resgate antecipado, etc, though RESGATE ANTECIPADO has its own rule)
                        postings = [
                            data.Posting(cash_account, amount.Amount(abs(valor), "BRL"), None, None, None, None),
                            data.Posting(asset_account, amount.Amount(-abs(qty), ticker), None, None, None, None),
                            data.Posting(f"Income:Investment:{inst}:Interest", None, None, None, None, None), # Balancing
                        ]

            elif mov_str == "RESGATE ANTECIPADO/":
                if qty is not None and valor is not None:
                    postings = [
                        data.Posting(cash_account, amount.Amount(abs(valor), "BRL"), None, None, None, None),
                        data.Posting(asset_account, None, None, None, None, None), # Let beancount reduce
                        data.Posting(f"Income:Investment:{inst}:Interest", None, None, None, None, None),
                    ]

            # 5. Fees
            elif "Taxa" in mov_str or "Cobrança" in mov_str:
                if valor is not None:
                    postings = [
                        data.Posting(f"Expenses:Investment:{inst}:Fees", amount.Amount(abs(valor), "BRL"), None, None, None, None),
                        data.Posting(cash_account, amount.Amount(-abs(valor), "BRL"), None, None, None, None),
                    ]
                    narration = f"Fee: {mov_str}"

            # 6. Fallback / Unknown
            else:
                meta["warning"] = "unknown_event_type"
                narration = f"Unknown Event: {mov_str}"
                if valor is not None:
                    postings = [
                        data.Posting(cash_account, amount.Amount(abs(valor), "BRL"), None, None, None, None),
                        data.Posting("Equity:Unknown", amount.Amount(-abs(valor), "BRL"), None, None, None, None),
                    ]
                else:
                    continue

            if postings:
                # Clean meta
                clean_meta = {k: v for k, v in meta.items() if v is not None}
                txn = data.Transaction(clean_meta, date, "*", None, narration, data.EMPTY_SET, data.EMPTY_SET, postings)
                entries.append(txn)

        return entries

    def _skip_tx(self, meta: data.Meta, date: datetime.date, narration: str) -> data.Transaction:
        return data.Transaction(meta, date, "!", None, narration, data.EMPTY_SET, data.EMPTY_SET, [
            data.Posting("Equity:Ignored", None, None, None, None, None)
        ])