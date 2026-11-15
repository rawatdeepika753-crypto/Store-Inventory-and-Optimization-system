# Store Inventory and Optimization System

A console-based, menu-driven C++ application that manages a store's products, sales, stock levels, restocking and expiry-based discounts. All data is kept in plain text files, so nothing is lost when the program closes. No database, internet, machine learning or external libraries are used - only the C++ standard library.

## Objectives and main features

- Add, display, search, update and delete products (with permanent storage)
- Sell products with stock checks, bill calculation and a saved sales history
- Detect low stock, create restock requests (FIFO queue) and receive them
- Check expiry dates, warn about expired products and discount near-expiry products
- Undo the last add / update / delete / sale (stack), including the files
- All data survives restarts (`products.txt`, `sales.txt`, `restock.txt`)

## Technologies used

C++17, standard library only (`<fstream>`, `<vector>`, `<queue>`, `<stack>`, `<algorithm>`, ...). The optional web front end uses Python 3 with Streamlit, pandas and Altair (see "Web front end"). Tested with g++ 13.3 on Linux; intended for Windows with MinGW g++ (see "Known limitations").

## DSA and OOP concepts actually implemented

| Concept | Where it is used |
|---|---|
| Singly linked list | `Product` nodes in `ProductManager` - the one shared in-memory product collection |
| Traversal | display, low-stock/expiry checks, saving to file, tail insertion |
| Dynamic memory | `new` when adding/loading a node, `delete` when removing a node and in the destructor |
| Sorting | `std::sort` of the search index by product ID (`ProductManager::rebuildSearchIndex`) |
| Binary search | `ProductManager::findProductById` on the sorted index |
| Queue (FIFO) | `std::queue<RestockRequest>` in `InventoryManager` - oldest request is received first |
| Stack (LIFO) | `std::stack<UndoRecord>` in `SystemManager` - last operation is undone first |
| OOP | classes `FileManager`, `ProductManager`, `SalesManager`, `InventoryManager`, `SystemManager`; encapsulated private data; constructors/destructor; no inheritance (not needed) |

There are **no global variables**. Modules receive pointers to the shared objects through their constructors.

## Folder and file descriptions

| File | Purpose |
|---|---|
| `Product.h` | Shared data model: `Product` (linked-list node), `SaleRecord`, `RestockRequest` |
| `ProductManager.h/.cpp` | Member 1 - linked list, CRUD, binary-search index |
| `SalesManager.h/.cpp` | Member 2 - selling, bills, sales history, sale reversal |
| `InventoryManager.h/.cpp` | Member 3 - low stock, restock queue, expiry analysis, discounts |
| `SystemManager.h/.cpp` | Member 4 - menus, integration, shared load/save, undo stack |
| `FileManager.h/.cpp` | All file reading/writing for the three data files |
| `main.cpp` | Entry point: creates `SystemManager`, runs the menu loop |
| `Utils.h/.cpp` | **Extra file.** Safe console input (re-asks until valid) and date functions, shared by all modules so this code is not duplicated |
| `products.txt` / `sales.txt` / `restock.txt` | Data files (sample products included; sales and restock start empty) |
| `app.py` | **Web front end** (Streamlit) - dashboard, POS, charts, data-structure visualisations |
| `inventory_core.py` | Python port of the C++ classes used by the web front end (same rules, same files) |
| `requirements.txt` / `.streamlit/config.toml` / `run_frontend.bat` | Python dependencies, dark theme, one-click Windows launcher |
| `docs/` | Project report (DOCX + PDF), presentation (PPTX + PDF), HLD/LLD diagrams and screenshots |

## Responsibilities of the four team members

- **Member 1 - Product Management and Data Storage:** `ProductManager` (linked list, add/display/search/update/delete, binary search index, connection to `FileManager`).
- **Member 2 - Sales Management:** `SalesManager` (sell, stock check, bill, reduce stock, sales history, save `sales.txt` and `products.txt`).
- **Member 3 - Inventory, Restocking and Expiry:** `InventoryManager` (low stock, restock queue, expiry/discount, `restock.txt`).
- **Member 4 - System Integration:** `SystemManager` and `main.cpp` (menus, input validation flow, loading/saving, undo stack, module testing). `FileManager` and `Utils` are shared infrastructure used by everyone.

## How the modules communicate

```
main.cpp -> SystemManager -> ProductManager ----\
                          -> SalesManager -------+--> FileManager --> products.txt / sales.txt / restock.txt
                          -> InventoryManager ---/
```

`SystemManager` owns one `FileManager` and one `ProductManager`. `SalesManager` and `InventoryManager` receive a **pointer to that same `ProductManager`**, so all modules read and change the same linked list. Sales finds products through `ProductManager::findProductById` (binary search); Inventory walks the list with `getHead()`.

## File-handling workflow

1. **Startup:** missing data files are created (existing files are never overwritten). Products are loaded into the linked list, sales history into a vector, restock requests into the queue.
2. **Every change** (add/update/delete/sale/restock/discount) saves immediately. A sale appends one line to `sales.txt`; history is never overwritten, except when the most recent sale is undone.
3. **Safe saving:** `products.txt` and `restock.txt` are written to a `.tmp` file first and only then replace the old file, so a failed write keeps the old data.
4. **Malformed lines** are skipped with a warning; the original file is copied to `<file>.bak` first so nothing is lost.
5. **Exit / "Save Data"** saves products and restock data again.

### File formats (`|` separated, lines starting with `#` are comments)

```
products.txt : id|name|category|quantity|reorderLevel|price|discountedPrice|expiryDate
sales.txt    : saleId|dateTime|productId|productName|quantity|unitPrice|totalBill
restock.txt  : requestId|productId|productName|currentQty|requestedQty|dateRequested|status|dateClosed
```
`status` is PENDING, FULFILLED or CANCELLED. PENDING lines are loaded back into the queue in file order, so FIFO order survives restarts. The `|` character is rejected in names/categories.

## Binary search implementation and complexity

The product list is a linked list, which cannot be binary-searched directly (no random access). So:

1. `rebuildSearchIndex()` walks the list and fills a `vector` of `(id, Product*)` pairs, then sorts it by ID - **O(n log n)**.
2. `findProductById()` runs ordinary binary search on that vector - **O(log n)**.
3. The index is built lazily and is **cleared whenever a node is added, deleted or the file is reloaded** (before any `delete`), so it never holds dangling pointers. Callers use the returned pointer immediately and never store it.

Searching many times without changes costs O(log n) each; after a change the next search rebuilds the index once.

### Time complexity of major operations

| Operation | Complexity |
|---|---|
| Add product (duplicate check + tail insert) | O(n log n) worst case for a rebuild, O(n) walk to the tail |
| Display all / low-stock check / expiry analysis / save | O(n) |
| Search by ID | O(log n) (after O(n log n) index rebuild when needed) |
| Delete product | O(n) |
| Sell a product | O(log n) search + O(n) save |
| Enqueue / dequeue restock request | O(1) |
| Push / pop undo record | O(1) |

## Business rules (defined explicitly)

- **Low stock:** `quantity <= reorderLevel` triggers a warning.
- **Target stock:** `2 x reorderLevel` (at least `reorderLevel + 1`). **Restock quantity = target - current quantity.** A product with a pending request is not requested twice.
- **Date format:** `YYYY-MM-DD` (years 1900-2100). Invalid dates (e.g. `2026-02-30`, `2026-13-01`) are rejected on input and when loading files. `NA` means the product does not expire.
- **Current date:** the program never assumes a date. In the expiry menu you enter today's date, or press Enter to use the computer's system clock. This also lets you test with any date.
- **Near expiry:** 0 to 7 days left. **Expired:** fewer than 0 days left (warned about, never discounted).
- **Discount:** 20% off the normal price for near-expiry products, applied only after you confirm. Constants are at the top of `InventoryManager.h`.
- **Price or expiry update** resets the discounted price to the normal price. Sales are billed at the discounted price.

## Undo (stack) - what it really does

Supported: **add product, update product, delete product, sell product.** Each one is pushed on a stack; "Undo" reverses the most recent one and rewrites the affected file(s):

- undo add -> product removed; undo delete -> product restored; undo update -> old values restored
- undo sale -> stock returned and the sale record removed from memory and `sales.txt`

Not undoable: receiving a restock and applying discounts. When one of these happens the undo history is **cleared** (and the program says so), because reversing older steps afterwards could corrupt stock numbers. The undo stack is not saved between runs.

## Menus

```
1. Product Management        (add / display / search / update / delete)
2. Sell a Product
3. Inventory and Restocking  (status / low stock / create requests / receive next request)
4. Expiry and Discount Analysis (show expired & near-expiry / apply discount)
5. View Sales History
6. View Restock Requests
7. Undo Last Supported Operation
8. Save Data
9. Exit
```
Every operation returns to the main menu afterwards. Invalid input is rejected and re-asked.

## Sample input/output (real output from the tested build)

```
Enter your choice (1-9): 2
--- Sell a Product ---
Enter product ID to sell: 101
Product : Basmati Rice 5kg (Grocery)
In stock: 40
Price   : Rs 520.00
Quantity to sell: 5
Bill: 5 x Rs 520.00 = Rs 2600.00
Confirm sale? (y/n): y
Sale completed. Sale ID 1, total Rs 2600.00.
```
```
--- Expiry Analysis (as of 2026-10-15) ---
ID      Name                  Expiry       Days left  Status                        Price       Now
102     Full Cream Milk 1L    2026-10-18           3  NEAR EXPIRY (eligible)        62.00     62.00
103     Whole Wheat Bread     2026-10-14          -1  EXPIRED                       45.00     45.00
WARNING: 1 product(s) are EXPIRED and should be removed from sale.
```

## Compilation and execution (Windows / MinGW)

Open a terminal in the `StoreInventorySystem` folder (in VS Code: Terminal > New Terminal):

```
g++ -std=c++17 *.cpp -o StoreInventorySystem.exe
.\StoreInventorySystem.exe
```
(Use `./StoreInventorySystem.exe` in Git Bash.) If `*.cpp` does not expand in PowerShell/cmd, list the files:
```
g++ -std=c++17 main.cpp SystemManager.cpp ProductManager.cpp SalesManager.cpp InventoryManager.cpp FileManager.cpp Utils.cpp -o StoreInventorySystem.exe
```

**Running from another folder:** the program reads/writes the data files in the *current* folder by default. To use a different data folder, pass it as an argument (the folder must exist; missing files in it are created):
```
C:\path\to\StoreInventorySystem.exe "C:\path\to\StoreInventorySystem"
```

## Web front end (Streamlit)

An interactive browser interface built with Python + Streamlit. It does **not** replace the C++ program: `inventory_core.py` is a class-by-class port of the C++ modules (linked list + sorted index + binary search, FIFO restock queue, LIFO undo stack, same validation and business rules), and it reads/writes the **same** `products.txt`, `sales.txt` and `restock.txt`. A sale made in the console shows up in the web app and vice versa.

**Run it** (Python 3.10 or newer):
```
pip install -r requirements.txt
streamlit run app.py
```
or double-click `run_frontend.bat`. The app opens at http://localhost:8501.

| Page | What you can do |
|---|---|
| Dashboard | KPI cards, expiry / low-stock alerts, stock-vs-reorder chart, stock value by category, revenue by day, top sellers |
| Products | Filterable catalogue (search, category, stock status, CSV export); add, update, delete (with confirmation); **Binary search lab** that draws the linked list and every low/mid/high step of the search |
| Point of Sale | Product cards with stock bars and expiry badges, a cart (+/-/remove), checkout with a printable receipt. Each cart line is saved as its own sale, and the whole cart is validated before anything is sold |
| Sales History | Date/product filters, revenue charts, CSV export |
| Inventory & Restock | Low-stock table (target / need), create requests, **FIFO queue visualisation**, receive the next request, history |
| Expiry & Discounts | Pick any "as of" date, days-until-expiry chart, apply the 20% near-expiry discount after a review dialog |
| Undo & System | **Undo stack visualisation** (top = next undo), undo / save / reload, view the raw data files, project/DSA summary |

Notes: the undo stack lives in the browser session (as in the console version, it is not saved). If the data files are changed by the console program while the web app is open, the app detects it and reloads them (clearing undo). Set the environment variable `INVENTORY_DATA` to use a different data folder.

## How to test file persistence

1. Run the program, add a product (menu 1 > 1), sell one item (menu 2), create restock requests (menu 3 > 3). Choose 9 to exit.
2. Open `products.txt`, `sales.txt` and `restock.txt` in VS Code - the changes are there.
3. Run the program again: the startup line shows the loaded counts, and menus 1>2, 5 and 6 show the same products, sales and pending requests.
4. Try undo: add a product, choose 7, then check that `products.txt` no longer contains it.
5. To reset the sample data, copy back the original three files from the ZIP.

## Known limitations and intentionally not implemented

- Tested on Linux with g++ 13.3 (including AddressSanitizer for memory errors/leaks); it was **not** run on Windows/MinGW in this environment. It uses only standard C++17, so it should compile there, but please run the compile command once.
- Undo covers only add/update/delete/sell and is lost when the program closes.
- Selling does not block expired products (the expiry check is a separate menu), and discounts are not removed automatically when time passes - update the product's price to reset a discount.
- Single user, no passwords, no multiple-item shopping cart (one product per sale).
- Product IDs are entered by the user (1-999999); names/categories may not contain `|`.
- Currency is shown as "Rs".
