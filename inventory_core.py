"""
inventory_core.py - Python back end for the Streamlit front end.

It is a faithful port of the C++ modules, so both programs follow the SAME
business rules and read/write the SAME data files:

    C++ class          ->  Python class here
    -----------------      --------------------------------------------------
    Product (node)     ->  Product          (singly linked list node)
    FileManager        ->  FileManager      (products.txt / sales.txt / restock.txt)
    ProductManager     ->  ProductManager   (linked list + sorted index + binary search)
    SalesManager       ->  SalesManager     (sell, bill, history, undo sale)
    InventoryManager   ->  InventoryManager (low stock, FIFO restock queue, expiry, discount)
    SystemManager      ->  SystemManager    (integration + LIFO undo stack)

Every method that the console version drives through std::cin takes plain
arguments here and raises InventoryError with a readable message on bad input,
so the web UI can show it.
"""
from __future__ import annotations

import math
import os
import re
import shutil
from collections import deque
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from enum import Enum
from typing import Iterator, Optional

# ---------------------------------------------------------------------------
# Constants (same values as the C++ headers)
# ---------------------------------------------------------------------------
MAX_PRODUCT_ID = 999_999
MAX_QUANTITY = 1_000_000
MAX_PRICE = 100_000_000.0
MAX_TEXT = 40

TARGET_STOCK_MULTIPLIER = 2   # target stock = 2 x reorder level
NEAR_EXPIRY_DAYS = 7          # 0..7 days left = near expiry
DISCOUNT_PERCENT = 20         # discount for near-expiry products

PRODUCTS_HEADER = (
    "# Store Inventory System - products.txt\n"
    "# Format: id|name|category|quantity|reorderLevel|price|discountedPrice|expiryDate\n"
    "# expiryDate is YYYY-MM-DD or NA. Lines starting with # are ignored.\n"
)
SALES_HEADER = (
    "# Store Inventory System - sales.txt (completed sales only)\n"
    "# Format: saleId|dateTime|productId|productName|quantity|unitPrice|totalBill\n"
)
RESTOCK_HEADER = (
    "# Store Inventory System - restock.txt\n"
    "# Format: requestId|productId|productName|currentQty|requestedQty|dateRequested|status|dateClosed\n"
    "# status is PENDING, FULFILLED or CANCELLED. PENDING lines are kept in FIFO order.\n"
)


class InventoryError(Exception):
    """Raised when an operation is rejected (bad input, not found, no stock...)."""


# ---------------------------------------------------------------------------
# Utils (port of Utils.cpp)
# ---------------------------------------------------------------------------
def round_money(value: float) -> float:
    return math.floor(value * 100.0 + 0.5) / 100.0


def fmt_money(value: float) -> str:
    return f"{value:.2f}"


def parse_date(text: str) -> Optional[date]:
    """Strict YYYY-MM-DD, years 1900-2100, real calendar dates only."""
    if len(text) != 10 or text[4] != "-" or text[7] != "-":
        return None
    if not (text[:4] + text[5:7] + text[8:]).isdigit():
        return None
    try:
        d = date(int(text[:4]), int(text[5:7]), int(text[8:]))
    except ValueError:
        return None
    return d if 1900 <= d.year <= 2100 else None


def is_valid_date(text: str) -> bool:
    return parse_date(text) is not None


def is_valid_expiry(text: str) -> bool:
    return text == "NA" or is_valid_date(text)


def days_between(from_date: str, to_date: str) -> int:
    a, b = parse_date(from_date), parse_date(to_date)
    if a is None or b is None:
        return 0
    return (b - a).days


def system_date() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def system_datetime() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def validate_text(value: str, label: str) -> str:
    value = (value or "").strip()
    if not value:
        raise InventoryError(f"{label} cannot be empty.")
    if "|" in value:
        raise InventoryError(f"{label}: the '|' character is not allowed (it separates fields in the data files).")
    if len(value) > MAX_TEXT:
        raise InventoryError(f"{label}: please use at most {MAX_TEXT} characters.")
    return value


def validate_int(value, label: str, lo: int, hi: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise InventoryError(f"{label} must be a whole number.") from None
    if number != value and not isinstance(value, (int, str)):
        raise InventoryError(f"{label} must be a whole number.")
    if not lo <= number <= hi:
        raise InventoryError(f"{label} must be between {lo} and {hi}.")
    return number


def validate_price(value) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise InventoryError("Price must be a number.") from None
    if not math.isfinite(number) or number < 0.01 or number > MAX_PRICE:
        raise InventoryError("Price must be at least Rs 0.01.")
    return round_money(number)


def validate_expiry(value: str) -> str:
    value = (value or "").strip()
    if value.upper() == "NA":
        return "NA"
    if is_valid_date(value):
        return value
    raise InventoryError("Invalid expiry date. Use a real calendar date as YYYY-MM-DD or NA.")


# ---------------------------------------------------------------------------
# Data model (port of Product.h)
# ---------------------------------------------------------------------------
@dataclass
class Product:
    id: int = 0
    name: str = ""
    category: str = ""
    quantity: int = 0
    reorder_level: int = 0
    price: float = 0.0
    discounted_price: float = 0.0          # equals price when no discount is active
    expiry_date: str = "NA"                # "YYYY-MM-DD" or "NA"
    next: Optional["Product"] = field(default=None, repr=False, compare=False)

    def snapshot(self) -> "Product":
        """Copy of the values, detached from the list (next = None)."""
        return replace(self, next=None)

    # Derived values used by the UI
    @property
    def is_low_stock(self) -> bool:
        return self.quantity <= self.reorder_level

    @property
    def has_discount(self) -> bool:
        return self.discounted_price < self.price - 0.005

    @property
    def target_stock(self) -> int:
        return max(self.reorder_level * TARGET_STOCK_MULTIPLIER, self.reorder_level + 1)

    def stock_status(self) -> str:
        if self.quantity == 0:
            return "OUT OF STOCK"
        if self.is_low_stock:
            return "LOW STOCK"
        return "OK"

    def days_until_expiry(self, today: str) -> Optional[int]:
        if self.expiry_date == "NA":
            return None
        return days_between(today, self.expiry_date)


@dataclass
class SaleRecord:
    sale_id: int = 0
    date_time: str = ""
    product_id: int = 0
    product_name: str = ""
    quantity: int = 0
    unit_price: float = 0.0
    total_bill: float = 0.0


@dataclass
class RestockRequest:
    request_id: int = 0
    product_id: int = 0
    product_name: str = ""
    current_quantity: int = 0
    requested_quantity: int = 0
    date_requested: str = ""
    status: str = "PENDING"
    date_closed: str = "-"


# ---------------------------------------------------------------------------
# FileManager (port of FileManager.cpp)
# ---------------------------------------------------------------------------
def _split(line: str) -> list[str]:
    # std::getline-based split drops a trailing empty field; mimic that.
    parts = line.split("|")
    if parts and parts[-1] == "":
        parts.pop()
    return parts


_INT_RE = re.compile(r"[+-]?\d+")


def _int(text: str) -> Optional[int]:
    return int(text) if _INT_RE.fullmatch(text) else None


def _float(text: str) -> Optional[float]:
    try:
        value = float(text)
    except ValueError:
        return None
    return value if math.isfinite(value) else None


class FileManager:
    def __init__(self, data_folder: str = "."):
        self.folder = data_folder
        self.products_path = os.path.join(data_folder, "products.txt")
        self.sales_path = os.path.join(data_folder, "sales.txt")
        self.restock_path = os.path.join(data_folder, "restock.txt")
        self.warnings: list[str] = []

    # --- helpers ---------------------------------------------------------
    def _create_if_missing(self, path: str, header: str) -> None:
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(header)
            self.warnings.append(f"Created missing data file: {os.path.basename(path)}")

    @staticmethod
    def _write_atomic(path: str, content: str) -> None:
        """Write to <file>.tmp first, then replace - a failed write keeps the old data."""
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        os.replace(tmp, path)

    def _backup(self, path: str) -> None:
        shutil.copyfile(path, path + ".bak")
        self.warnings.append(f"A backup of the original file was saved as {os.path.basename(path)}.bak")

    def _data_lines(self, path: str) -> Iterator[tuple[int, str]]:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for number, line in enumerate(f, start=1):
                line = line.strip()
                if line and not line.startswith("#"):
                    yield number, line

    def mtimes(self) -> tuple:
        return tuple(os.path.getmtime(p) if os.path.exists(p) else 0
                     for p in (self.products_path, self.sales_path, self.restock_path))

    def initialize_files(self) -> None:
        self._create_if_missing(self.products_path, PRODUCTS_HEADER)
        self._create_if_missing(self.sales_path, SALES_HEADER)
        self._create_if_missing(self.restock_path, RESTOCK_HEADER)

    # --- products --------------------------------------------------------
    @staticmethod
    def _parse_product(line: str) -> Optional[Product]:
        f = _split(line)
        if len(f) != 8:
            return None
        pid, qty, reorder = _int(f[0]), _int(f[3]), _int(f[4])
        price, disc = _float(f[5]), _float(f[6])
        if pid is None or pid <= 0 or not f[1] or not f[2]:
            return None
        if qty is None or qty < 0 or reorder is None or reorder < 0:
            return None
        if price is None or price <= 0 or disc is None or disc <= 0 or disc > price + 0.005:
            return None
        if not is_valid_expiry(f[7]):
            return None
        return Product(pid, f[1], f[2], qty, reorder, price, disc, f[7])

    def load_products(self) -> list[Product]:
        products, seen, skipped = [], set(), 0
        for number, line in self._data_lines(self.products_path):
            p = self._parse_product(line)
            if p is None:
                self.warnings.append(f"products.txt line {number} is malformed and was skipped.")
                skipped += 1
            elif p.id in seen:
                self.warnings.append(f"products.txt line {number} repeats product ID {p.id} and was skipped.")
                skipped += 1
            else:
                seen.add(p.id)
                products.append(p)
        if skipped:
            self._backup(self.products_path)
        return products

    def save_products(self, head: Optional[Product]) -> None:
        lines = [PRODUCTS_HEADER]
        node = head
        while node is not None:
            lines.append(f"{node.id}|{node.name}|{node.category}|{node.quantity}|{node.reorder_level}|"
                         f"{fmt_money(node.price)}|{fmt_money(node.discounted_price)}|{node.expiry_date}\n")
            node = node.next
        self._write_atomic(self.products_path, "".join(lines))

    # --- sales -----------------------------------------------------------
    @staticmethod
    def _sale_line(s: SaleRecord) -> str:
        return (f"{s.sale_id}|{s.date_time}|{s.product_id}|{s.product_name}|{s.quantity}|"
                f"{fmt_money(s.unit_price)}|{fmt_money(s.total_bill)}\n")

    def load_sales(self) -> list[SaleRecord]:
        sales, skipped = [], 0
        for number, line in self._data_lines(self.sales_path):
            f = _split(line)
            ok = len(f) == 7
            if ok:
                sid, pid, qty = _int(f[0]), _int(f[2]), _int(f[4])
                unit, total = _float(f[5]), _float(f[6])
                ok = (sid is not None and sid > 0 and pid is not None and pid > 0 and qty is not None
                      and qty > 0 and unit is not None and unit >= 0 and total is not None and total >= 0
                      and bool(f[1]) and bool(f[3]))
            if not ok:
                self.warnings.append(f"sales.txt line {number} is malformed and was skipped.")
                skipped += 1
                continue
            sales.append(SaleRecord(sid, f[1], pid, f[3], qty, unit, total))
        if skipped:
            self._backup(self.sales_path)
        return sales

    def append_sale(self, sale: SaleRecord) -> None:
        with open(self.sales_path, "a", encoding="utf-8", newline="\n") as f:
            f.write(self._sale_line(sale))

    def save_all_sales(self, sales: list[SaleRecord]) -> None:
        self._write_atomic(self.sales_path, SALES_HEADER + "".join(self._sale_line(s) for s in sales))

    # --- restock ---------------------------------------------------------
    def load_restock(self) -> tuple[deque, list[RestockRequest]]:
        pending, closed, skipped = deque(), [], 0
        for number, line in self._data_lines(self.restock_path):
            f = _split(line)
            ok = len(f) == 8
            if ok:
                rid, pid, cur, req = _int(f[0]), _int(f[1]), _int(f[3]), _int(f[4])
                ok = (rid is not None and rid > 0 and pid is not None and pid > 0 and cur is not None
                      and cur >= 0 and req is not None and req > 0 and bool(f[2]) and bool(f[5])
                      and f[6] in ("PENDING", "FULFILLED", "CANCELLED"))
            if not ok:
                self.warnings.append(f"restock.txt line {number} is malformed and was skipped.")
                skipped += 1
                continue
            r = RestockRequest(rid, pid, f[2], cur, req, f[5], f[6], f[7])
            (pending.append if r.status == "PENDING" else closed.append)(r)   # file order = FIFO
        if skipped:
            self._backup(self.restock_path)
        return pending, closed

    def save_restock(self, pending: deque, closed: list[RestockRequest]) -> None:
        def row(r: RestockRequest) -> str:
            return (f"{r.request_id}|{r.product_id}|{r.product_name}|{r.current_quantity}|"
                    f"{r.requested_quantity}|{r.date_requested}|{r.status}|{r.date_closed}\n")
        body = "".join(row(r) for r in closed) + "".join(row(r) for r in pending)
        self._write_atomic(self.restock_path, RESTOCK_HEADER + body)


# ---------------------------------------------------------------------------
# ProductManager (port of ProductManager.cpp): singly linked list + binary search
# ---------------------------------------------------------------------------
class ProductManager:
    def __init__(self, file_manager: FileManager):
        self.fm = file_manager
        self.head: Optional[Product] = None
        self.count = 0
        self._index: list[tuple[int, Product]] = []   # sorted by id, rebuilt lazily
        self._index_valid = False

    # --- list helpers ----------------------------------------------------
    def __iter__(self) -> Iterator[Product]:
        node = self.head
        while node is not None:
            yield node
            node = node.next

    def _invalidate(self) -> None:
        self._index = []
        self._index_valid = False

    def load(self) -> None:
        self.head, self.count = None, 0
        tail = None
        for p in self.fm.load_products():
            if tail is None:
                self.head = p
            else:
                tail.next = p
            tail = p
            self.count += 1
        self._invalidate()

    def save(self) -> None:
        self.fm.save_products(self.head)

    # --- binary search ---------------------------------------------------
    def rebuild_index(self) -> None:
        """Walk the list into an array of (id, node) and sort it by id: O(n log n)."""
        self._index = sorted(((p.id, p) for p in self), key=lambda e: e[0])
        self._index_valid = True

    def find(self, pid: int) -> Optional[Product]:
        return self.binary_search(pid)[0]

    def binary_search(self, pid: int) -> tuple[Optional[Product], list[dict]]:
        """Binary search on the sorted index: O(log n). Also returns every step (for the UI)."""
        if not self._index_valid:
            self.rebuild_index()
        steps, low, high = [], 0, len(self._index) - 1
        while low <= high:
            mid = low + (high - low) // 2
            mid_id = self._index[mid][0]
            result = "found" if mid_id == pid else ("go right" if mid_id < pid else "go left")
            steps.append({"low": low, "mid": mid, "high": high, "mid_id": mid_id, "result": result})
            if mid_id == pid:
                return self._index[mid][1], steps
            if mid_id < pid:
                low = mid + 1
            else:
                high = mid - 1
        return None, steps

    def sorted_ids(self) -> list[int]:
        if not self._index_valid:
            self.rebuild_index()
        return [e[0] for e in self._index]

    # --- core operations -------------------------------------------------
    def insert(self, product: Product) -> bool:
        if product.id <= 0 or self.find(product.id) is not None:
            return False
        node = product.snapshot()
        if self.head is None:
            self.head = node
        else:
            tail = self.head
            while tail.next is not None:
                tail = tail.next
            tail.next = node
        self.count += 1
        self._invalidate()
        return True

    def delete(self, pid: int) -> bool:
        previous, current = None, self.head
        while current is not None and current.id != pid:
            previous, current = current, current.next
        if current is None:
            return False
        self._invalidate()
        if previous is None:
            self.head = current.next
        else:
            previous.next = current.next
        current.next = None
        self.count -= 1
        return True

    def restore(self, snap: Product) -> bool:
        node = self.find(snap.id)
        if node is None:
            return False
        for attr in ("name", "category", "quantity", "reorder_level", "price",
                     "discounted_price", "expiry_date"):
            setattr(node, attr, getattr(snap, attr))
        return True

    # --- "menu" operations (validated, saved) ----------------------------
    def add_product(self, pid, name, category, quantity, reorder_level, price, expiry) -> Product:
        pid = validate_int(pid, "Product ID", 1, MAX_PRODUCT_ID)
        if self.find(pid) is not None:
            raise InventoryError(f"A product with ID {pid} already exists. Nothing was added.")
        price = validate_price(price)
        product = Product(
            id=pid,
            name=validate_text(name, "Product name"),
            category=validate_text(category, "Category"),
            quantity=validate_int(quantity, "Quantity", 0, MAX_QUANTITY),
            reorder_level=validate_int(reorder_level, "Reorder level", 1, MAX_QUANTITY),
            price=price,
            discounted_price=price,
            expiry_date=validate_expiry(expiry),
        )
        self.insert(product)
        self.save()
        return product.snapshot()

    def update_product(self, pid, name, category, quantity, reorder_level, price, expiry
                       ) -> tuple[Product, bool]:
        """Returns (old snapshot, discount_was_reset)."""
        node = self.find(int(pid))
        if node is None:
            raise InventoryError(f"Product with ID {pid} was not found.")
        updated = node.snapshot()
        updated.name = validate_text(name, "Name")
        updated.category = validate_text(category, "Category")
        updated.quantity = validate_int(quantity, "Quantity", 0, MAX_QUANTITY)
        updated.reorder_level = validate_int(reorder_level, "Reorder level", 1, MAX_QUANTITY)
        updated.price = validate_price(price)
        updated.expiry_date = validate_expiry(expiry)
        reset = False
        if updated.price != node.price or updated.expiry_date != node.expiry_date:
            updated.discounted_price = updated.price   # new price / expiry resets any discount
            reset = True
        if updated == node.snapshot():
            raise InventoryError("No changes were made.")
        before = node.snapshot()
        self.restore(updated)
        self.save()
        return before, reset

    def delete_product(self, pid: int) -> Product:
        node = self.find(int(pid))
        if node is None:
            raise InventoryError(f"Product with ID {pid} was not found.")
        copy = node.snapshot()
        self.delete(copy.id)
        self.save()
        return copy


# ---------------------------------------------------------------------------
# SalesManager (port of SalesManager.cpp)
# ---------------------------------------------------------------------------
class SalesManager:
    def __init__(self, product_manager: ProductManager, file_manager: FileManager):
        self.pm = product_manager
        self.fm = file_manager
        self.history: list[SaleRecord] = []
        self.next_sale_id = 1

    def load(self) -> None:
        self.history = self.fm.load_sales()
        self.next_sale_id = max((s.sale_id for s in self.history), default=0) + 1

    def check_sale(self, pid: int, quantity: int) -> Product:
        if self.pm.count == 0:
            raise InventoryError("There are no products in the store yet.")
        product = self.pm.find(int(pid))   # binary search
        if product is None:
            raise InventoryError(f"Product with ID {pid} was not found. Sale cancelled.")
        if product.quantity == 0:
            raise InventoryError(f"'{product.name}' is out of stock. Sale cancelled.")
        quantity = validate_int(quantity, "Quantity", 1, MAX_QUANTITY)
        if quantity > product.quantity:
            raise InventoryError(f"Insufficient stock for '{product.name}': only {product.quantity} "
                                 f"available, requested {quantity}. Sale cancelled.")
        return product

    def sell(self, pid: int, quantity: int) -> SaleRecord:
        product = self.check_sale(pid, quantity)
        unit = product.discounted_price
        total = round_money(unit * quantity)
        product.quantity -= quantity
        try:
            self.pm.save()
        except OSError:
            product.quantity += quantity   # an unsaved sale is not a completed sale
            raise InventoryError("Sale cancelled because stock could not be saved.") from None
        sale = SaleRecord(self.next_sale_id, system_datetime(), product.id, product.name,
                          quantity, unit, total)
        self.next_sale_id += 1
        self.history.append(sale)
        self.fm.append_sale(sale)
        return sale

    def undo_sale(self, sale: SaleRecord) -> None:
        if not self.history or self.history[-1].sale_id != sale.sale_id:
            raise InventoryError("Cannot undo: this is not the most recent sale.")
        product = self.pm.find(sale.product_id)
        if product is None:
            raise InventoryError(f"Cannot undo: product {sale.product_id} no longer exists.")
        product.quantity += sale.quantity
        self.history.pop()
        self.next_sale_id = sale.sale_id
        self.pm.save()
        self.fm.save_all_sales(self.history)


# ---------------------------------------------------------------------------
# InventoryManager (port of InventoryManager.cpp)
# ---------------------------------------------------------------------------
class InventoryManager:
    def __init__(self, product_manager: ProductManager, file_manager: FileManager):
        self.pm = product_manager
        self.fm = file_manager
        self.pending: deque[RestockRequest] = deque()    # FIFO queue
        self.closed: list[RestockRequest] = []           # fulfilled / cancelled history
        self.next_request_id = 1

    def load(self) -> None:
        self.pending, self.closed = self.fm.load_restock()
        all_ids = [r.request_id for r in self.closed] + [r.request_id for r in self.pending]
        self.next_request_id = max(all_ids, default=0) + 1

    def save(self) -> None:
        self.fm.save_restock(self.pending, self.closed)

    def has_pending(self, pid: int) -> bool:
        return any(r.product_id == pid for r in self.pending)

    def low_stock(self) -> list[Product]:
        return [p for p in self.pm if p.is_low_stock]

    def create_restock_requests(self) -> tuple[list[RestockRequest], int]:
        """Queues requests for low-stock products. Returns (created, already_pending_count)."""
        created, already = [], 0
        today = system_date()
        for p in self.pm:
            if not p.is_low_stock:
                continue
            if self.has_pending(p.id):
                already += 1
                continue
            r = RestockRequest(self.next_request_id, p.id, p.name, p.quantity,
                               p.target_stock - p.quantity, today, "PENDING", "-")
            self.next_request_id += 1
            self.pending.append(r)                         # enqueue
            created.append(r)
        if created:
            self.save()
        return created, already

    def fulfill_next(self) -> tuple[RestockRequest, Optional[Product]]:
        """Dequeue the oldest request. Returns (closed request, product or None if cancelled)."""
        if not self.pending:
            raise InventoryError("There are no pending restock requests.")
        request = replace(self.pending[0])
        product = self.pm.find(request.product_id)
        if product is None:
            request.status = "CANCELLED"
        else:
            product.quantity += request.requested_quantity
            try:
                self.pm.save()
            except OSError:
                product.quantity -= request.requested_quantity
                raise InventoryError("Could not save products.txt. The request stays pending.") from None
            request.status = "FULFILLED"
        self.pending.popleft()                             # dequeue
        request.date_closed = system_date()
        self.closed.append(request)
        self.save()
        return request, (product.snapshot() if product else None)

    # --- expiry ----------------------------------------------------------
    def expiry_report(self, today: str) -> list[dict]:
        rows = []
        for p in self.pm:
            days = p.days_until_expiry(today)
            if days is None:
                status = "NO EXPIRY"
            elif days < 0:
                status = "EXPIRED"
            elif days <= NEAR_EXPIRY_DAYS:
                status = "NEAR EXPIRY (discounted)" if p.has_discount else "NEAR EXPIRY (eligible)"
            else:
                status = "FRESH"
            rows.append({"product": p, "days": days, "status": status})
        return rows

    def eligible_for_discount(self, today: str) -> list[Product]:
        out = []
        for p in self.pm:
            days = p.days_until_expiry(today)
            if days is not None and 0 <= days <= NEAR_EXPIRY_DAYS and not p.has_discount:
                out.append(p)
        return out

    def apply_discounts(self, today: str) -> list[tuple[str, float, float]]:
        changed = []
        for p in self.eligible_for_discount(today):
            p.discounted_price = round_money(p.price * (100 - DISCOUNT_PERCENT) / 100.0)
            changed.append((p.name, p.price, p.discounted_price))
        if changed:
            self.pm.save()
        return changed


# ---------------------------------------------------------------------------
# SystemManager (port of SystemManager.cpp): integration + undo stack
# ---------------------------------------------------------------------------
class UndoType(Enum):
    ADD_PRODUCT = "Add product"
    DELETE_PRODUCT = "Delete product"
    UPDATE_PRODUCT = "Update product"
    SELL_PRODUCT = "Sell product"


@dataclass
class UndoRecord:
    type: UndoType
    product: Optional[Product] = None   # added / deleted product, or OLD values
    sale: Optional[SaleRecord] = None
    when: str = field(default_factory=system_datetime)

    def describe(self) -> str:
        if self.type == UndoType.SELL_PRODUCT:
            return f"Sale #{self.sale.sale_id}: {self.sale.quantity} x {self.sale.product_name}"
        return f"{self.type.value}: {self.product.name} (ID {self.product.id})"


class SystemManager:
    def __init__(self, data_folder: str = "."):
        self.fm = FileManager(data_folder)
        self.products = ProductManager(self.fm)
        self.sales = SalesManager(self.products, self.fm)
        self.inventory = InventoryManager(self.products, self.fm)
        self.undo_stack: list[UndoRecord] = []    # LIFO: append = push, pop = pop
        self.loaded_mtimes: tuple = ()
        self.initialize()

    def initialize(self) -> None:
        self.fm.warnings.clear()
        self.fm.initialize_files()
        self.products.load()
        self.sales.load()
        self.inventory.load()
        self.loaded_mtimes = self.fm.mtimes()

    def files_changed_externally(self) -> bool:
        return self.fm.mtimes() != self.loaded_mtimes

    def _mark_saved(self) -> None:
        self.loaded_mtimes = self.fm.mtimes()

    def clear_undo(self) -> bool:
        had = bool(self.undo_stack)
        self.undo_stack.clear()
        return had

    # --- operations that record undo -------------------------------------
    def add_product(self, *args) -> Product:
        p = self.products.add_product(*args)
        self.undo_stack.append(UndoRecord(UndoType.ADD_PRODUCT, product=p))
        self._mark_saved()
        return p

    def update_product(self, *args) -> bool:
        before, reset = self.products.update_product(*args)
        self.undo_stack.append(UndoRecord(UndoType.UPDATE_PRODUCT, product=before))
        self._mark_saved()
        return reset

    def delete_product(self, pid: int) -> Product:
        p = self.products.delete_product(pid)
        self.undo_stack.append(UndoRecord(UndoType.DELETE_PRODUCT, product=p))
        self._mark_saved()
        return p

    def sell(self, pid: int, quantity: int) -> SaleRecord:
        sale = self.sales.sell(pid, quantity)
        self.undo_stack.append(UndoRecord(UndoType.SELL_PRODUCT, sale=sale))
        self._mark_saved()
        return sale

    def checkout(self, cart: dict[int, int]) -> list[SaleRecord]:
        """Sells several products; validates the whole cart first so nothing half-completes."""
        if not cart:
            raise InventoryError("The cart is empty.")
        for pid, qty in cart.items():
            self.sales.check_sale(pid, qty)
        return [self.sell(pid, qty) for pid, qty in cart.items()]

    # --- operations that clear undo (as in the C++ version) --------------
    def fulfill_next_restock(self):
        request, product = self.inventory.fulfill_next()
        cleared = request.status == "FULFILLED" and self.clear_undo()
        self._mark_saved()
        return request, product, cleared

    def create_restock_requests(self):
        result = self.inventory.create_restock_requests()
        self._mark_saved()
        return result

    def apply_discounts(self, today: str):
        changed = self.inventory.apply_discounts(today)
        cleared = bool(changed) and self.clear_undo()
        self._mark_saved()
        return changed, cleared

    # --- undo -------------------------------------------------------------
    def undo(self) -> str:
        if not self.undo_stack:
            raise InventoryError("Nothing to undo. (Supported: add, update, delete product and sell product.)")
        record = self.undo_stack.pop()
        try:
            if record.type == UndoType.ADD_PRODUCT:
                if not self.products.delete(record.product.id):
                    raise InventoryError("The operation could not be undone.")
                msg = f"Undone: removed product '{record.product.name}'."
            elif record.type == UndoType.DELETE_PRODUCT:
                if not self.products.insert(record.product):
                    raise InventoryError("The operation could not be undone.")
                msg = f"Undone: restored deleted product '{record.product.name}'."
            elif record.type == UndoType.UPDATE_PRODUCT:
                if not self.products.restore(record.product):
                    raise InventoryError("The operation could not be undone.")
                msg = f"Undone: restored old values of product '{record.product.name}'."
            else:
                self.sales.undo_sale(record.sale)
                msg = (f"Undone: sale #{record.sale.sale_id} reversed, "
                       f"{record.sale.quantity} unit(s) returned to stock.")
            if record.type != UndoType.SELL_PRODUCT:
                self.products.save()
        finally:
            self._mark_saved()
        return msg

    def save_all(self) -> None:
        self.products.save()
        self.inventory.save()
        self._mark_saved()
