"""
app.py - Streamlit front end for the Store Inventory and Optimization System.

Run:   streamlit run app.py
It uses inventory_core.py (a Python port of the C++ modules) and works on the
same products.txt / sales.txt / restock.txt files as the console program.
"""
from __future__ import annotations

import html
import os
from datetime import date, datetime

import altair as alt
import pandas as pd
import streamlit as st

from inventory_core import (
    DISCOUNT_PERCENT, MAX_PRODUCT_ID, MAX_QUANTITY, NEAR_EXPIRY_DAYS, TARGET_STOCK_MULTIPLIER,
    InventoryError, SystemManager, UndoType, fmt_money, system_date,
)

# Data folder: the project folder by default, or the INVENTORY_DATA environment variable.
DATA_FOLDER = os.environ.get("INVENTORY_DATA") or os.path.dirname(os.path.abspath(__file__))

st.set_page_config(
    page_title="Store Inventory System",
    page_icon="🏪",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Colours (dark chart palette) and styling
# ---------------------------------------------------------------------------
GOOD, WARNING, SERIOUS, CRITICAL = "#0ca30c", "#fab219", "#ec835a", "#d03b3b"
BLUE, VIOLET = "#3987e5", "#9085e9"
INK, INK2, MUTED = "#f0efec", "#c3c2b7", "#898781"
GRID, AXIS = "#2c2c2a", "#383835"

STATUS_ICON = {"OK": "🟢", "LOW STOCK": "🟠", "OUT OF STOCK": "🔴"}
EXPIRY_ICON = {"EXPIRED": "🔴", "NEAR EXPIRY (eligible)": "🟠", "NEAR EXPIRY (discounted)": "🏷️",
               "FRESH": "🟢", "NO EXPIRY": "⚪"}

st.markdown(
    f"""
<style>
:root {{
  --good:{GOOD}; --warning:{WARNING}; --serious:{SERIOUS}; --critical:{CRITICAL};
  --blue:{BLUE}; --violet:{VIOLET};
  --card: rgba(127,127,127,0.07); --card-border: rgba(127,127,127,0.20);
}}
.block-container {{ padding-top: 2.2rem; padding-bottom: 3rem; }}
[data-testid="stMetricValue"] {{ font-size: clamp(1.25rem, 2.2vw, 1.9rem); }}
.hero {{
  border-radius: 18px; padding: 26px 30px; margin-bottom: 18px; color: #fff;
  background: linear-gradient(120deg, #1c5cab 0%, #3987e5 45%, #6250d6 100%);
  box-shadow: 0 10px 30px rgba(57,135,229,0.25); position: relative; overflow: hidden;
}}
.hero:after {{
  content:""; position:absolute; right:-60px; top:-60px; width:220px; height:220px;
  border-radius:50%; background: rgba(255,255,255,0.08);
}}
.hero h1 {{ font-size: 1.9rem; margin: 0 0 4px 0; color:#fff; padding:0; }}
.hero p {{ margin: 0; opacity: .9; font-size: 1rem; }}
.page-title {{ display:flex; align-items:center; gap:12px; margin-bottom: 6px; }}
.page-title .ico {{
  font-size: 1.6rem; width: 52px; height: 52px; display:flex; align-items:center; justify-content:center;
  border-radius: 14px; background: linear-gradient(135deg, rgba(57,135,229,.35), rgba(98,80,214,.35));
}}
.page-title h2 {{ margin:0; padding:0; font-size:1.6rem; }}
.page-title .sub {{ opacity:.7; font-size:.92rem; }}
.alert {{
  border-radius: 12px; padding: 12px 16px; border: 1px solid var(--card-border);
  background: var(--card); margin-bottom: 10px; border-left: 5px solid var(--c);
}}
.alert b {{ font-size: 1.05rem; }}
.chip {{
  display:inline-block; padding: 2px 10px; border-radius: 999px; font-size: .78rem; font-weight: 600;
  border: 1px solid var(--card-border); background: var(--card); margin: 2px 4px 2px 0;
}}
.pcard {{
  border-radius: 14px; padding: 14px; border: 1px solid var(--card-border); background: var(--card);
  min-height: 205px; transition: transform .15s ease, box-shadow .15s ease;
}}
.pcard:hover {{ transform: translateY(-3px); box-shadow: 0 8px 22px rgba(0,0,0,.25); }}
.pcard .name {{ font-weight: 700; font-size: 1.0rem; line-height:1.25; }}
.pcard .cat {{ opacity:.65; font-size: .8rem; margin-bottom: 8px; }}
.pcard .price {{ font-size: 1.2rem; font-weight: 800; white-space: nowrap; }}
.pcard .name {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.pcard .old {{ text-decoration: line-through; opacity: .55; font-size: .85rem; margin-left: 6px; }}
.bar {{ height: 6px; border-radius: 6px; background: rgba(127,127,127,.25); overflow:hidden; margin-top:8px; }}
.bar > div {{ height: 100%; border-radius: 6px; }}
.receipt {{
  font-family: ui-monospace, Consolas, monospace; background: #fbfaf5; color: #111;
  border-radius: 10px; padding: 18px 20px; font-size: .88rem;
}}
.receipt .c {{ text-align:center; }}
.receipt hr {{ border: none; border-top: 1px dashed #999; margin: 8px 0; }}
.receipt table {{ width:100%; border-collapse: collapse; }}
.receipt table, .receipt tr, .receipt td {{ border: none !important; background: transparent !important; color:#111; }}
.receipt td {{ padding: 2px 0 !important; }}
.receipt td.r {{ text-align:right; }}
/* data-structure visualisations */
.ds-row {{ display:flex; flex-wrap:wrap; align-items:center; gap:6px; margin: 6px 0 10px; }}
.node {{
  border-radius: 10px; padding: 8px 12px; border: 1px solid var(--card-border); background: var(--card);
  font-weight: 700; font-family: ui-monospace, Consolas, monospace; text-align:center; min-width: 54px;
}}
.node small {{ display:block; font-weight: 400; opacity: .7; font-family: system-ui, sans-serif; font-size: .7rem; }}
.node.dim {{ opacity: .25; }}
.node.mid {{ border: 2px solid var(--blue); background: rgba(57,135,229,.22); }}
.node.hit {{ border: 2px solid var(--good); background: rgba(12,163,12,.25); }}
.node.front {{ border: 2px solid var(--warning); }}
.arrow {{ opacity: .6; font-weight: 700; }}
.step-label {{ font-size: .82rem; opacity: .8; margin-top: 4px; }}
.stack {{ display:flex; flex-direction:column; gap:6px; max-width: 560px; }}
.stack .node {{ text-align:left; font-family: system-ui, sans-serif; font-weight:600; }}
.stack .top {{ border: 2px solid var(--violet); background: rgba(144,133,233,.18); }}
section[data-testid="stSidebar"] .side-stat {{
  display:flex; justify-content:space-between; padding: 6px 2px; border-bottom: 1px solid var(--card-border);
  font-size: .9rem;
}}
</style>
""",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------
def get_system() -> SystemManager:
    # A rebuilt object is also needed when Streamlit hot-reloads inventory_core after a code edit.
    if not isinstance(st.session_state.get("system"), SystemManager):
        st.session_state.system = SystemManager(DATA_FOLDER)
        st.session_state.setdefault("cart", {})
        st.session_state.setdefault("flashes", [])
        st.session_state.setdefault("activity", [])
        for w in st.session_state.system.fm.warnings:
            flash(w, "warning")
    return st.session_state.system


def flash(message: str, kind: str = "success") -> None:
    st.session_state.setdefault("flashes", []).append((kind, message))


def log(icon: str, message: str) -> None:
    st.session_state.setdefault("activity", []).insert(0, (datetime.now().strftime("%H:%M:%S"), icon, message))
    del st.session_state.activity[50:]


def show_flashes() -> None:
    icons = {"success": "✅", "warning": "⚠️", "error": "❌", "info": "ℹ️"}
    for kind, message in st.session_state.get("flashes", []):
        st.toast(message, icon=icons.get(kind, "ℹ️"))
    st.session_state.flashes = []


def run_action(fn, *args):
    """Runs a back-end call, turning InventoryError / OS errors into a visible message."""
    try:
        return True, fn(*args)
    except InventoryError as exc:
        st.error(str(exc), icon="🚫")
    except OSError as exc:
        st.error(f"File error: {exc}. Is a data file open in another program?", icon="💾")
    return False, None


def money(value: float) -> str:
    return f"Rs {value:,.2f}"


def page_header(icon: str, title: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="page-title"><div class="ico">{icon}</div>'
        f'<div><h2>{html.escape(title)}</h2><div class="sub">{html.escape(subtitle)}</div></div></div>',
        unsafe_allow_html=True,
    )


def product_label(p) -> str:
    return f"{p.id} · {p.name}  —  {money(p.discounted_price)}  ({p.quantity} in stock)"


def products_frame(system: SystemManager, today: str) -> pd.DataFrame:
    rows = []
    for p in system.products:
        days = p.days_until_expiry(today)
        status = p.stock_status()
        rows.append({
            "ID": p.id, "Name": p.name, "Category": p.category, "Qty": p.quantity,
            "Reorder": p.reorder_level, "Target": p.target_stock,
            "Stock level": min(p.quantity / p.target_stock, 1.0) if p.target_stock else 0.0,
            "Price": p.price, "Selling price": p.discounted_price,
            "Discount": "20% off" if p.has_discount else "",
            "Expiry": p.expiry_date, "Days left": days,
            "Status": f"{STATUS_ICON[status]} {status}",
            "Restock pending": "⏳ yes" if system.inventory.has_pending(p.id) else "",
            "Stock value": round(p.quantity * p.discounted_price, 2),
            "_status": status,
        })
    return pd.DataFrame(rows)


def chart_style(chart: alt.Chart) -> alt.Chart:
    return (
        chart.properties(background="transparent")
        .configure_view(strokeWidth=0)
        .configure_axis(gridColor=GRID, domainColor=AXIS, tickColor=AXIS, labelColor=INK2,
                        titleColor=INK2, labelFontSize=12, titleFontSize=12, titleFontWeight="normal")
        .configure_legend(labelColor=INK2, titleColor=INK2, orient="top", labelFontSize=12, labelLimit=0,
                          symbolType="square")
    )


# ---------------------------------------------------------------------------
# Dialogs
# ---------------------------------------------------------------------------
@st.dialog("🧾 Receipt", width="small")
def receipt_dialog(sales) -> None:
    total = sum(s.total_bill for s in sales)
    rows = "".join(
        f"<tr><td>{html.escape(s.product_name)}<br><small>{s.quantity} x {fmt_money(s.unit_price)}"
        f"  (sale #{s.sale_id})</small></td><td class='r'>{fmt_money(s.total_bill)}</td></tr>"
        for s in sales
    )
    st.markdown(
        f"""<div class="receipt">
<div class="c"><b>STORE INVENTORY SYSTEM</b><br>Tax invoice / cash memo<br>{sales[0].date_time}</div>
<hr><table>{rows}</table><hr>
<table><tr><td><b>TOTAL</b></td><td class='r'><b>Rs {fmt_money(total)}</b></td></tr>
<tr><td>Items</td><td class='r'>{sum(s.quantity for s in sales)}</td></tr></table>
<hr><div class="c">Thank you for shopping with us!</div></div>""",
        unsafe_allow_html=True,
    )
    text = "\n".join(f"#{s.sale_id} {s.product_name} {s.quantity} x {fmt_money(s.unit_price)} = "
                     f"{fmt_money(s.total_bill)}" for s in sales) + f"\nTOTAL Rs {fmt_money(total)}\n"
    st.download_button("Download receipt", text, file_name=f"receipt_{sales[0].sale_id}.txt",
                       icon=":material/download:", width="stretch")


@st.dialog("Delete product?")
def delete_dialog(pid: int) -> None:
    system = get_system()
    p = system.products.find(pid)
    if p is None:
        st.write("This product no longer exists.")
        return
    st.markdown(f"**{p.name}** (ID {p.id}) · {p.category} · {p.quantity} in stock")
    st.caption("You can bring it back with **Undo** (it is pushed on the undo stack).")
    c1, c2 = st.columns(2)
    if c1.button("Cancel", width="stretch"):
        st.rerun()
    if c2.button("Delete", type="primary", icon=":material/delete:", width="stretch"):
        ok, deleted = run_action(system.delete_product, pid)
        if ok:
            flash(f"Deleted '{deleted.name}'.")
            log("🗑️", f"Deleted product {deleted.id} · {deleted.name}")
            st.rerun()


@st.dialog("Apply near-expiry discount")
def discount_dialog(today: str) -> None:
    system = get_system()
    eligible = system.inventory.eligible_for_discount(today)
    if not eligible:
        st.info("No products are eligible for a discount.")
        return
    st.write(f"{len(eligible)} product(s) expire within {NEAR_EXPIRY_DAYS} days of **{today}** "
             f"and will get **{DISCOUNT_PERCENT}% off**:")
    st.dataframe(pd.DataFrame([{
        "Product": p.name, "Expiry": p.expiry_date, "Price": money(p.price),
        "New price": money(round(p.price * (100 - DISCOUNT_PERCENT) / 100, 2))} for p in eligible]),
        hide_index=True)
    if system.undo_stack:
        st.warning("Discounts cannot be undone, so the undo history will be cleared.", icon="⚠️")
    if st.button("Apply discount", type="primary", icon=":material/sell:", width="stretch"):
        ok, result = run_action(system.apply_discounts, today)
        if ok:
            changed, cleared = result
            flash(f"Discount applied to {len(changed)} product(s).")
            if cleared:
                flash("Undo history cleared: discounts cannot be undone.", "info")
            for name, old, new in changed:
                log("🏷️", f"Discount: {name} Rs {fmt_money(old)} → Rs {fmt_money(new)}")
            st.rerun()


# ---------------------------------------------------------------------------
# Page: Dashboard
# ---------------------------------------------------------------------------
def page_dashboard() -> None:
    system = get_system()
    today = system_date()
    df = products_frame(system, today)
    sales = system.sales.history
    revenue = sum(s.total_bill for s in sales)
    expiry = system.inventory.expiry_report(today)
    expired = [r for r in expiry if r["status"] == "EXPIRED"]
    near = [r for r in expiry if r["status"].startswith("NEAR")]
    low = [p for p in system.products if p.is_low_stock]
    out = [p for p in low if p.quantity == 0]

    st.markdown(
        f"""<div class="hero"><h1>🏪 Store Inventory &amp; Optimization System</h1>
<p>Live overview for {datetime.now().strftime('%A, %d %B %Y')} · {system.products.count} products ·
{len(sales)} sales recorded · data stored in plain text files</p></div>""",
        unsafe_allow_html=True,
    )

    k = st.columns(3) + st.columns(3)
    k[0].metric("📦 Products", system.products.count, border=True)
    k[1].metric("🧮 Units in stock", f"{int(df['Qty'].sum()) if not df.empty else 0:,}", border=True)
    k[2].metric("💎 Stock value", f"Rs {df['Stock value'].sum() if not df.empty else 0:,.0f}", border=True)
    k[3].metric("💰 Revenue", f"Rs {revenue:,.0f}", f"{len(sales)} sales", delta_color="off", delta_arrow="off",
                border=True)
    k[4].metric("📉 Low stock", len(low), f"{len(out)} out of stock" if out else None,
                delta_color="inverse", delta_arrow="off", border=True)
    k[5].metric("🚚 Pending restocks", len(system.inventory.pending), border=True)

    # Alerts
    a1, a2, a3 = st.columns(3)
    with a1:
        names = ", ".join(r["product"].name for r in expired) or "None - great!"
        st.markdown(f'<div class="alert" style="--c:{CRITICAL}">🔴 <b>{len(expired)} expired</b><br>'
                    f'<small>{html.escape(names)}</small></div>', unsafe_allow_html=True)
    with a2:
        names = ", ".join(r["product"].name for r in near) or "None in the next 7 days"
        st.markdown(f'<div class="alert" style="--c:{WARNING}">🟠 <b>{len(near)} near expiry</b><br>'
                    f'<small>{html.escape(names)}</small></div>', unsafe_allow_html=True)
    with a3:
        names = ", ".join(p.name for p in low) or "All products above reorder level"
        st.markdown(f'<div class="alert" style="--c:{SERIOUS}">📉 <b>{len(low)} at/below reorder level</b><br>'
                    f'<small>{html.escape(names)}</small></div>', unsafe_allow_html=True)

    if df.empty:
        st.info("No products yet - add some on the **Products** page.")
        return

    c1, c2 = st.columns([3, 2])
    with c1:
        with st.container(border=True):
            st.markdown("**Stock level vs reorder level**")
            st.caption("Bar = units in stock · white tick = reorder level · hover for details")
            base = alt.Chart(df).encode(y=alt.Y("Name:N", sort="-x", title=None))
            bars = base.mark_bar(cornerRadiusEnd=4, height={"band": 0.6}).encode(
                x=alt.X("Qty:Q", title="Units"),
                color=alt.Color("_status:N", title="Status",
                                scale=alt.Scale(domain=["OK", "LOW STOCK", "OUT OF STOCK"],
                                                range=[GOOD, WARNING, CRITICAL])),
                tooltip=["ID", "Name", "Category", "Qty", "Reorder", "Target",
                         alt.Tooltip("_status:N", title="Status")],
            )
            ticks = base.mark_tick(color=INK, thickness=2, size=18).encode(
                x="Reorder:Q", tooltip=["Name", alt.Tooltip("Reorder:Q", title="Reorder level")])
            st.altair_chart(chart_style((bars + ticks).properties(height=max(260, 30 * len(df)))),
                            width="stretch", theme=None)
    with c2:
        with st.container(border=True):
            st.markdown("**Stock value by category**")
            st.caption("Units × current selling price")
            cat = df.groupby("Category", as_index=False).agg(Value=("Stock value", "sum"), Units=("Qty", "sum"),
                                                             Products=("ID", "count"))
            chart = alt.Chart(cat).mark_bar(cornerRadiusEnd=4, color=BLUE, height={"band": 0.6}).encode(
                y=alt.Y("Category:N", sort="-x", title=None),
                x=alt.X("Value:Q", title="Rs"),
                tooltip=["Category", alt.Tooltip("Value:Q", format=",.2f", title="Value (Rs)"),
                         "Units", "Products"],
            )
            st.altair_chart(chart_style(chart.properties(height=max(260, 34 * len(cat)))),
                            width="stretch", theme=None)

    c3, c4 = st.columns([3, 2])
    with c3:
        with st.container(border=True):
            st.markdown("**Revenue by day**")
            if sales:
                sdf = pd.DataFrame([{"Date": s.date_time[:10], "Revenue": s.total_bill, "Units": s.quantity}
                                    for s in sales]).groupby("Date", as_index=False).sum()
                chart = alt.Chart(sdf).mark_bar(cornerRadiusEnd=4, color=BLUE,
                                                size=max(8, min(40, 500 // len(sdf)))).encode(
                    x=alt.X("Date:O", title=None), y=alt.Y("Revenue:Q", title="Rs"),
                    tooltip=["Date", alt.Tooltip("Revenue:Q", format=",.2f"), "Units"])
                st.altair_chart(chart_style(chart.properties(height=260)), width="stretch", theme=None)
            else:
                st.info("No sales yet. Open **Point of Sale** to make the first sale.", icon="🛒")
    with c4:
        with st.container(border=True):
            st.markdown("**Top sellers**")
            if sales:
                tdf = pd.DataFrame([{"Product": s.product_name, "Revenue": s.total_bill, "Units": s.quantity}
                                    for s in sales]).groupby("Product", as_index=False).sum()
                tdf = tdf.nlargest(8, "Revenue")
                chart = alt.Chart(tdf).mark_bar(cornerRadiusEnd=4, color=BLUE, height={"band": 0.6}).encode(
                    y=alt.Y("Product:N", sort="-x", title=None), x=alt.X("Revenue:Q", title="Rs"),
                    tooltip=["Product", alt.Tooltip("Revenue:Q", format=",.2f"), "Units"])
                st.altair_chart(chart_style(chart.properties(height=max(120, 36 * len(tdf)))),
                                width="stretch", theme=None)
            else:
                st.caption("Best-selling products will appear here.")

    if st.session_state.get("activity"):
        with st.expander("Recent activity (this session)", icon=":material/history:"):
            for t, icon, msg in st.session_state.activity[:12]:
                st.markdown(f"`{t}` {icon} {msg}")


# ---------------------------------------------------------------------------
# Page: Products
# ---------------------------------------------------------------------------
def expiry_inputs(prefix: str, current: str = "NA") -> str:
    has = st.toggle("Product expires", value=current != "NA", key=f"{prefix}_has_exp")
    if has:
        default = date.fromisoformat(current) if current != "NA" else date.today()
        d = st.date_input("Expiry date", value=default, min_value=date(1900, 1, 1),
                          max_value=date(2100, 12, 31), key=f"{prefix}_exp_{current}")
        return d.isoformat()
    return "NA"


def page_products() -> None:
    system = get_system()
    page_header("📦", "Product Management", "Add, browse, search, update and delete products (singly linked list)")
    today = system_date()
    df = products_frame(system, today)

    tab_browse, tab_add, tab_edit, tab_search = st.tabs(
        [":material/inventory_2: Catalogue", ":material/add_circle: Add product",
         ":material/edit: Update / delete", ":material/search: Binary search lab"])

    # -- Catalogue -------------------------------------------------------
    with tab_browse:
        if df.empty:
            st.info("No products found. Add one in the **Add product** tab.")
        else:
            f1, f2, f3 = st.columns([2, 3, 2])
            query = f1.text_input("Search name / ID", placeholder="e.g. milk or 104",
                                  icon=":material/search:")
            cats = sorted(df["Category"].unique())
            chosen = f2.pills("Category", cats, selection_mode="multi")
            status = f3.segmented_control("Stock", ["All", "OK", "Low", "Out"], default="All")
            view = df
            if query:
                q = query.lower()
                view = view[view["Name"].str.lower().str.contains(q, regex=False) |
                            view["ID"].astype(str).str.contains(q, regex=False)]
            if chosen:
                view = view[view["Category"].isin(chosen)]
            if status == "OK":
                view = view[view["_status"] == "OK"]
            elif status == "Low":
                view = view[view["_status"] == "LOW STOCK"]
            elif status == "Out":
                view = view[view["_status"] == "OUT OF STOCK"]

            st.dataframe(
                view.drop(columns=["_status", "Days left"]),
                hide_index=True, width="stretch", height=min(42 + 35 * len(view), 520),
                column_config={
                    "ID": st.column_config.NumberColumn(format="%d", width="small"),
                    "Qty": st.column_config.NumberColumn(width="small"),
                    "Reorder": st.column_config.NumberColumn(width="small"),
                    "Target": st.column_config.NumberColumn(width="small",
                                                            help=f"{TARGET_STOCK_MULTIPLIER} × reorder level"),
                    "Stock level": st.column_config.ProgressColumn(
                        "Stock vs target", format="percent", min_value=0, max_value=1),
                    "Price": st.column_config.NumberColumn(format="Rs %.2f"),
                    "Selling price": st.column_config.NumberColumn(format="Rs %.2f"),
                    "Stock value": st.column_config.NumberColumn(format="Rs %.2f"),
                },
            )
            st.caption(f"Showing {len(view)} of {len(df)} products · list order = linked-list order "
                       f"(new products are appended at the tail)")
            st.download_button("Export CSV", view.drop(columns=["_status"]).to_csv(index=False),
                               "products.csv", icon=":material/download:")

    # -- Add -------------------------------------------------------------
    with tab_add:
        ids = set(system.products.sorted_ids())
        suggestion = max(ids, default=100) + 1
        with st.container(border=True):
            c1, c2, c3 = st.columns([1, 2, 2])
            pid = c1.number_input("Product ID", 1, MAX_PRODUCT_ID, value=min(suggestion, MAX_PRODUCT_ID),
                                  step=1, key="add_id", help="Must be unique (1-999999)")
            name = c2.text_input("Product name", max_chars=40, key="add_name")
            existing_cats = sorted({p.category for p in system.products})
            category = c3.selectbox("Category", existing_cats, index=None, accept_new_options=True,
                                    placeholder="Choose or type a new one", key="add_cat")
            c4, c5, c6 = st.columns(3)
            qty = c4.number_input("Quantity in stock", 0, MAX_QUANTITY, value=0, step=1, key="add_qty")
            reorder = c5.number_input("Reorder level", 1, MAX_QUANTITY, value=10, step=1, key="add_reorder",
                                      help="A warning is shown when stock is at or below this level")
            price = c6.number_input("Price (Rs)", min_value=0.01, value=10.00, step=1.0, format="%.2f",
                                    key="add_price")
            expiry = expiry_inputs("add")
            if pid in ids:
                st.warning(f"ID {pid} is already used. Next free ID: {suggestion}.", icon="⚠️")
            if st.button("Add product", type="primary", icon=":material/add:"):
                ok, p = run_action(system.add_product, pid, name, category or "", qty, reorder, price, expiry)
                if ok:
                    flash(f"Product '{p.name}' added (ID {p.id}).")
                    log("➕", f"Added product {p.id} · {p.name}")
                    for k in ("add_name", "add_cat"):
                        st.session_state.pop(k, None)
                    st.session_state.pop("add_id", None)
                    st.rerun()

    # -- Update / delete -------------------------------------------------
    with tab_edit:
        if system.products.count == 0:
            st.info("There are no products to update.")
        else:
            options = [p.id for p in system.products]
            labels = {p.id: f"{p.id} · {p.name}" for p in system.products}
            pid = st.selectbox("Choose a product", options, format_func=labels.get, key="edit_pick")
            p = system.products.find(pid)
            with st.container(border=True):
                st.caption("Change any field and press **Save changes**. Changing the price or expiry date "
                           "resets an active discount.")
                c1, c2 = st.columns(2)
                name = c1.text_input("Name", value=p.name, max_chars=40, key=f"e_name_{pid}")
                cats = sorted({x.category for x in system.products})
                category = c2.selectbox("Category", cats, index=cats.index(p.category), accept_new_options=True,
                                        key=f"e_cat_{pid}")
                c3, c4, c5 = st.columns(3)
                qty = c3.number_input("Quantity", 0, MAX_QUANTITY, value=p.quantity, step=1, key=f"e_qty_{pid}")
                reorder = c4.number_input("Reorder level", 1, MAX_QUANTITY, value=max(p.reorder_level, 1),
                                          step=1, key=f"e_re_{pid}")
                price = c5.number_input("Price (Rs)", min_value=0.01, value=float(p.price), step=1.0,
                                        format="%.2f", key=f"e_price_{pid}")
                expiry = expiry_inputs(f"e_{pid}", p.expiry_date)
                if p.has_discount:
                    st.info(f"Active discount: selling at {money(p.discounted_price)} instead of "
                            f"{money(p.price)}.", icon="🏷️")
                row = st.container(horizontal=True)
                if row.button("Save changes", type="primary", icon=":material/save:"):
                    ok, reset = run_action(system.update_product, pid, name, category or "", qty, reorder,
                                           price, expiry)
                    if ok:
                        flash(f"Product {pid} updated.")
                        if reset:
                            flash("Discounted price was reset to the (new) normal price.", "info")
                        log("✏️", f"Updated product {pid} · {name}")
                        st.rerun()
                if row.button("Delete product", icon=":material/delete:"):
                    delete_dialog(pid)

    # -- Binary search lab -----------------------------------------------
    with tab_search:
        binary_search_lab(system)


def binary_search_lab(system: SystemManager) -> None:
    st.markdown("Products live in a **singly linked list** (no random access), so a sorted "
                "**index array** of `(id, pointer)` is built from it with `std::sort` – *O(n log n)* – "
                "and searched with **binary search** – *O(log n)*.")
    if system.products.count == 0:
        st.info("Add products first.")
        return
    ids = system.products.sorted_ids()
    c1, c2 = st.columns([1, 3])
    target = c1.number_input("Product ID to find", 1, MAX_PRODUCT_ID, value=ids[len(ids) // 2], step=1)
    found, steps = system.products.binary_search(int(target))

    # Linked list view
    st.markdown("**1 · Linked list (insertion order)**")
    nodes = []
    for p in system.products:
        cls = "node hit" if found is not None and p.id == found.id else "node"
        nodes.append(f'<div class="{cls}">{p.id}<small>{html.escape(p.name[:14])}</small></div>')
    st.markdown('<div class="ds-row"><span class="chip">head</span>'
                + '<span class="arrow">→</span>'.join(nodes)
                + '<span class="arrow">→</span><span class="chip">NULL</span></div>', unsafe_allow_html=True)

    st.markdown(f"**2 · Sorted index + binary search for `{int(target)}`**")
    for n, s in enumerate(steps, start=1):
        cells = []
        for i, pid in enumerate(ids):
            cls = "node"
            if i < s["low"] or i > s["high"]:
                cls += " dim"
            if i == s["mid"]:
                cls += " hit" if s["result"] == "found" else " mid"
            tag = " ".join(t for t, j in (("low", s["low"]), ("mid", s["mid"]), ("high", s["high"])) if j == i)
            cells.append(f'<div class="{cls}">{pid}<small>[{i}] {tag}</small></div>')
        verdict = {"found": "✅ match!", "go right": f"{s['mid_id']} < {int(target)} → search right half",
                   "go left": f"{s['mid_id']} > {int(target)} → search left half"}[s["result"]]
        st.markdown(f'<div class="step-label">Step {n}: low={s["low"]}, high={s["high"]}, '
                    f'mid={s["mid"]} → index[{s["mid"]}] = {s["mid_id"]} · {verdict}</div>'
                    f'<div class="ds-row">{"".join(cells)}</div>', unsafe_allow_html=True)

    if found is not None:
        st.success(f"Found **{found.name}** in {len(steps)} comparison(s) "
                   f"(a linear scan of the list could need up to {len(ids)}).", icon="🎯")
        st.dataframe(products_frame(system, system_date()).query("ID == @found.id")
                     .drop(columns=["_status", "Stock level"]), hide_index=True, width="stretch")
    else:
        st.error(f"Product with ID {int(target)} was not found after {len(steps)} comparison(s).", icon="🔍")


# ---------------------------------------------------------------------------
# Page: Point of sale
# ---------------------------------------------------------------------------
def cart_add(pid: int, delta: int) -> None:
    system = get_system()
    p = system.products.find(pid)
    cart = st.session_state.cart
    new = cart.get(pid, 0) + delta
    if p is None or new <= 0:
        cart.pop(pid, None)
    elif new > p.quantity:
        flash(f"Only {p.quantity} unit(s) of '{p.name}' in stock.", "warning")
    else:
        cart[pid] = new


def page_pos() -> None:
    system = get_system()
    page_header("🛒", "Point of Sale", "Pick products, review the bill and check out — stock and sales.txt update instantly")
    today = system_date()
    cart: dict = st.session_state.cart
    # drop items whose product vanished (e.g. deleted)
    for pid in [pid for pid in cart if system.products.find(pid) is None]:
        cart.pop(pid)

    left, right = st.columns([2.2, 1], gap="large")
    with left:
        query = st.text_input("Search", placeholder="Search products by name or ID…",
                              icon=":material/search:", label_visibility="collapsed")
        cats = sorted({p.category for p in system.products})
        chosen = st.pills("Category", cats, selection_mode="multi", label_visibility="collapsed")
        items = [p for p in system.products
                 if (not query or query.lower() in p.name.lower() or query in str(p.id))
                 and (not chosen or p.category in chosen)]
        if not items:
            st.info("No products match.")
        cols = st.columns(3)
        for i, p in enumerate(items):
            with cols[i % 3]:
                in_cart = cart.get(p.id, 0)
                left_qty = p.quantity - in_cart
                status = p.stock_status()
                colour = {"OK": GOOD, "LOW STOCK": WARNING, "OUT OF STOCK": CRITICAL}[status]
                pct = min(p.quantity / p.target_stock, 1) * 100 if p.target_stock else 0
                days = p.days_until_expiry(today)
                badge = ""
                if days is not None and days < 0:
                    badge = '<span class="chip" style="color:#ff8a8a">⚠ expired</span>'
                elif days is not None and days <= NEAR_EXPIRY_DAYS:
                    badge = f'<span class="chip">⏳ {days}d left</span>'
                if p.has_discount:
                    badge += f'<span class="chip">🏷️ {DISCOUNT_PERCENT}% off</span>'
                old = f'<span class="old">{fmt_money(p.price)}</span>' if p.has_discount else ""
                st.markdown(
                    f"""<div class="pcard"><div class="name" title="{html.escape(p.name)}">{html.escape(p.name)}</div>
<div class="cat">#{p.id} · {html.escape(p.category)}</div>
<div class="price">Rs {fmt_money(p.discounted_price)}{old}</div>
<div style="font-size:.82rem;margin-top:4px">{STATUS_ICON[status]} {p.quantity} in stock
{f'· <b>{in_cart} in cart</b>' if in_cart else ''}</div>
<div class="bar"><div style="width:{pct:.0f}%;background:{colour}"></div></div>
<div style="margin-top:6px">{badge}</div></div>""",
                    unsafe_allow_html=True,
                )
                st.button("Add" if left_qty > 0 else "Sold out", key=f"add_{p.id}",
                          icon=":material/add_shopping_cart:", disabled=left_qty <= 0, width="stretch",
                          on_click=cart_add, args=(p.id, 1))
                st.write("")

    with right:
        with st.container(border=True):
            st.markdown("### 🧺 Cart")
            if not cart:
                st.caption("Your cart is empty. Click **Add to cart** on a product.")
            total = 0.0
            for pid, qty in list(cart.items()):
                p = system.products.find(pid)
                line = round(p.discounted_price * qty, 2)
                total += line
                st.markdown(f"**{p.name}**  \n{qty} × {money(p.discounted_price)} = **{money(line)}**")
                b1, b2, b3 = st.columns(3)
                b1.button("", key=f"m_{pid}", icon=":material/remove:", on_click=cart_add, args=(pid, -1),
                          width="stretch")
                b2.button("", key=f"p_{pid}", icon=":material/add:", on_click=cart_add, args=(pid, 1),
                          disabled=qty >= p.quantity, width="stretch")
                b3.button("", key=f"r_{pid}", icon=":material/delete:", on_click=cart_add, args=(pid, -qty),
                          width="stretch")
                if p.days_until_expiry(today) is not None and p.days_until_expiry(today) < 0:
                    st.caption("⚠️ This product is past its expiry date.")
                st.divider()
            if cart:
                st.metric("Total bill", money(total), f"{sum(cart.values())} item(s)", delta_color="off",
                          delta_arrow="off")
                if st.button("Checkout", type="primary", icon=":material/point_of_sale:", width="stretch"):
                    ok, sales = run_action(system.checkout, dict(cart))
                    if ok:
                        st.session_state.cart = {}
                        st.session_state.receipt = sales
                        for s in sales:
                            log("💰", f"Sale #{s.sale_id}: {s.quantity} × {s.product_name} = {money(s.total_bill)}")
                            p = system.products.find(s.product_id)
                            if p and p.is_low_stock:
                                flash(f"Stock of '{p.name}' is now {p.quantity} (reorder level "
                                      f"{p.reorder_level}).", "warning")
                        flash(f"Sale completed: {money(sum(s.total_bill for s in sales))}.")
                        st.session_state.celebrate = True
                        st.rerun()
                if st.button("Clear cart", icon=":material/remove_shopping_cart:", width="stretch"):
                    st.session_state.cart = {}
                    st.rerun()
        st.caption("Each cart line is saved as its own sale record (one product per sale, like the "
                   "console version) and can be reversed with **Undo**.")

    if st.session_state.pop("celebrate", False):
        st.balloons()
    if "receipt" in st.session_state:
        receipt_dialog(st.session_state.pop("receipt"))


# ---------------------------------------------------------------------------
# Page: Inventory & restocking
# ---------------------------------------------------------------------------
def page_inventory() -> None:
    system = get_system()
    inv = system.inventory
    page_header("🚚", "Inventory & Restocking", "Low-stock detection and a FIFO restock queue")
    df = products_frame(system, system_date())
    low = inv.low_stock()

    k = st.columns(4)
    k[0].metric("Total units", f"{int(df['Qty'].sum()) if not df.empty else 0:,}", border=True)
    k[1].metric("Low stock", len(low), border=True)
    k[2].metric("Out of stock", sum(p.quantity == 0 for p in low), border=True)
    k[3].metric("Pending requests", len(inv.pending), border=True)

    t1, t2, t3 = st.tabs([":material/warning: Low stock", ":material/queue: Restock queue (FIFO)",
                          ":material/table: Inventory status"])
    with t1:
        st.caption(f"Rule: warning when **quantity ≤ reorder level**. Target stock = "
                   f"**{TARGET_STOCK_MULTIPLIER} × reorder level** (at least reorder + 1). "
                   f"Order quantity = target − current.")
        if not low:
            st.success("No products are low on stock.", icon="✅")
        else:
            st.dataframe(pd.DataFrame([{
                "ID": p.id, "Name": p.name, "Qty": p.quantity, "Reorder": p.reorder_level,
                "Target": p.target_stock, "Need": p.target_stock - p.quantity,
                "Status": f"{STATUS_ICON[p.stock_status()]} {p.stock_status()}",
                "Request pending?": "⏳ yes" if inv.has_pending(p.id) else "no"} for p in low]),
                hide_index=True, width="stretch")
            new = [p for p in low if not inv.has_pending(p.id)]
            if st.button(f"Create restock requests ({len(new)} new)", type="primary",
                         icon=":material/playlist_add:", disabled=not new):
                ok, result = run_action(system.create_restock_requests)
                if ok:
                    created, already = result
                    for r in created:
                        log("📝", f"Restock request #{r.request_id}: {r.product_name} +{r.requested_quantity}")
                    flash(f"{len(created)} restock request(s) added to the queue.")
                    st.rerun()
            if not new:
                st.caption("All low-stock products already have a pending request.")

    with t2:
        st.caption("Requests are **enqueued at the rear** and **received from the front** – the oldest "
                   "request is always fulfilled first (std::queue / deque).")
        if not inv.pending:
            st.info("The queue is empty. Create requests from the **Low stock** tab.", icon="📭")
        else:
            cards = []
            for i, r in enumerate(inv.pending):
                tag = "FRONT · next" if i == 0 else ("REAR" if i == len(inv.pending) - 1 else f"#{i + 1}")
                cards.append(f'<div class="node {"front" if i == 0 else ""}" style="min-width:130px">'
                             f'<small>{tag}</small>Req #{r.request_id}<small>{html.escape(r.product_name)}<br>'
                             f'+{r.requested_quantity} units · {r.date_requested}</small></div>')
            st.markdown('<div class="ds-row"><span class="chip">dequeue ⟵</span>'
                        + '<span class="arrow">←</span>'.join(cards)
                        + '<span class="chip">⟵ enqueue</span></div>', unsafe_allow_html=True)
            front = inv.pending[0]
            if system.undo_stack:
                st.caption("ℹ️ Receiving stock clears the undo history (it cannot be undone safely).")
            if st.button(f"Receive next: #{front.request_id} {front.product_name} (+{front.requested_quantity})",
                         type="primary", icon=":material/local_shipping:"):
                ok, result = run_action(system.fulfill_next_restock)
                if ok:
                    request, product, cleared = result
                    if request.status == "FULFILLED":
                        flash(f"Request #{request.request_id} fulfilled: {product.name} stock is now "
                              f"{product.quantity}.")
                    else:
                        flash(f"Request #{request.request_id} cancelled: product {request.product_id} "
                              f"no longer exists.", "warning")
                    if cleared:
                        flash("Undo history cleared: received stock cannot be undone safely.", "info")
                    log("📦", f"Restock #{request.request_id} {request.status.lower()}: {request.product_name}")
                    st.rerun()
        st.markdown("**History (closed requests)**")
        if inv.closed:
            st.dataframe(pd.DataFrame([{
                "Req #": r.request_id, "Product ID": r.product_id, "Product": r.product_name,
                "Stock then": r.current_quantity, "Ordered": r.requested_quantity,
                "Requested": r.date_requested,
                "Status": ("✅ " if r.status == "FULFILLED" else "✖️ ") + r.status,
                "Closed": r.date_closed} for r in reversed(inv.closed)]), hide_index=True, width="stretch")
        else:
            st.caption("No closed requests yet.")

    with t3:
        if df.empty:
            st.info("No products found.")
        else:
            st.dataframe(df[["ID", "Name", "Qty", "Reorder", "Stock level", "Status", "Expiry", "Restock pending"]],
                         hide_index=True, width="stretch",
                         column_config={"Stock level": st.column_config.ProgressColumn(
                             "Stock vs target", format="percent", min_value=0, max_value=1)})


# ---------------------------------------------------------------------------
# Page: Expiry & discounts
# ---------------------------------------------------------------------------
def page_expiry() -> None:
    system = get_system()
    page_header("⏳", "Expiry & Discount Analysis",
                f"Near expiry = 0–{NEAR_EXPIRY_DAYS} days left · near-expiry products can get {DISCOUNT_PERCENT}% off")
    c1, c2 = st.columns([1, 3])
    as_of = c1.date_input("Analyse as of", value=date.today(), min_value=date(1900, 1, 1),
                          max_value=date(2100, 12, 31), help="Pick any date to test the rules")
    today = as_of.isoformat()
    rows = system.inventory.expiry_report(today)
    counts = {s: sum(r["status"] == s for r in rows) for s in EXPIRY_ICON}
    eligible = system.inventory.eligible_for_discount(today)

    k = st.columns(5)
    k[0].metric("🔴 Expired", counts["EXPIRED"], border=True)
    k[1].metric("🟠 Near expiry", counts["NEAR EXPIRY (eligible)"] + counts["NEAR EXPIRY (discounted)"], border=True)
    k[2].metric("🏷️ Discounted", sum(p.has_discount for p in system.products), border=True)
    k[3].metric("🟢 Fresh", counts["FRESH"], border=True)
    k[4].metric("⚪ No expiry", counts["NO EXPIRY"], border=True)

    if counts["EXPIRED"]:
        st.error(f"{counts['EXPIRED']} product(s) are **EXPIRED** and should be removed from sale.", icon="🚨")

    dated = [r for r in rows if r["days"] is not None]
    if dated:
        with st.container(border=True):
            st.markdown("**Days until expiry**")
            st.caption(f"Dashed lines mark today (0) and the {NEAR_EXPIRY_DAYS}-day near-expiry window")
            cdf = pd.DataFrame([{
                "Name": r["product"].name, "Days left": r["days"], "Expiry": r["product"].expiry_date,
                "Group": "Expired" if r["days"] < 0 else ("Near expiry" if r["days"] <= NEAR_EXPIRY_DAYS
                                                          else "Fresh"),
                "Status": r["status"]} for r in dated])
            bars = alt.Chart(cdf).mark_bar(cornerRadius=4, height={"band": 0.6}).encode(
                y=alt.Y("Name:N", sort="x", title=None),
                x=alt.X("Days left:Q", title="Days left"),
                color=alt.Color("Group:N", title="Status",
                                scale=alt.Scale(domain=["Expired", "Near expiry", "Fresh"],
                                                range=[CRITICAL, WARNING, GOOD])),
                tooltip=["Name", "Expiry", "Days left", "Status"])
            rules = alt.Chart(pd.DataFrame({"x": [0, NEAR_EXPIRY_DAYS]})).mark_rule(
                color=MUTED, strokeDash=[4, 4], strokeWidth=1.5).encode(x="x:Q")
            st.altair_chart(chart_style((bars + rules).properties(height=max(220, 32 * len(cdf)))),
                            width="stretch", theme=None)

    show_all = st.toggle("Show all products (not only those needing attention)", value=False)
    table = [r for r in rows if show_all or r["status"] in
             ("EXPIRED", "NEAR EXPIRY (eligible)", "NEAR EXPIRY (discounted)")]
    if table:
        st.dataframe(pd.DataFrame([{
            "ID": r["product"].id, "Name": r["product"].name, "Expiry": r["product"].expiry_date,
            "Days left": r["days"], "Status": f'{EXPIRY_ICON[r["status"]]} {r["status"]}',
            "Price": r["product"].price, "Now": r["product"].discounted_price} for r in table]),
            hide_index=True, width="stretch",
            column_config={"Price": st.column_config.NumberColumn(format="Rs %.2f"),
                           "Now": st.column_config.NumberColumn(format="Rs %.2f")})
    else:
        st.success("No products are expired or near expiry on this date.", icon="✅")

    st.markdown("#### 🏷️ Discounts")
    st.write(f"**{len(eligible)}** product(s) are eligible for a {DISCOUNT_PERCENT}% discount "
             f"(0–{NEAR_EXPIRY_DAYS} days left and not already discounted). Expired products are never discounted.")
    if st.button("Review & apply discount", type="primary", icon=":material/sell:", disabled=not eligible):
        discount_dialog(today)


# ---------------------------------------------------------------------------
# Page: Sales history
# ---------------------------------------------------------------------------
def page_sales() -> None:
    system = get_system()
    page_header("📈", "Sales History", "Every completed sale, stored line by line in sales.txt")
    sales = system.sales.history
    if not sales:
        st.info("No sales have been recorded yet. Use **Point of Sale** to sell a product.", icon="🛒")
        return
    df = pd.DataFrame([{
        "Sale ID": s.sale_id, "Date/Time": s.date_time, "Date": s.date_time[:10], "Product ID": s.product_id,
        "Product": s.product_name, "Qty": s.quantity, "Unit price": s.unit_price, "Total": s.total_bill}
        for s in sales])
    dates = pd.to_datetime(df["Date"], errors="coerce")
    lo, hi = dates.min().date(), dates.max().date()

    f1, f2 = st.columns([1, 2])
    rng = f1.date_input("Date range", value=(lo, hi), min_value=lo, max_value=hi)
    prods = f2.multiselect("Products", sorted(df["Product"].unique()), placeholder="All products")
    view = df
    if isinstance(rng, tuple) and len(rng) == 2:
        mask = (dates.dt.date >= rng[0]) & (dates.dt.date <= rng[1])
        view = view[mask]
    if prods:
        view = view[view["Product"].isin(prods)]

    k = st.columns(4)
    k[0].metric("Sales", len(view), border=True)
    k[1].metric("Revenue", money(view["Total"].sum()), border=True)
    k[2].metric("Units sold", int(view["Qty"].sum()), border=True)
    k[3].metric("Average bill", money(view["Total"].mean() if len(view) else 0), border=True)

    if not view.empty:
        c1, c2 = st.columns(2)
        with c1, st.container(border=True):
            st.markdown("**Revenue by product**")
            g = view.groupby("Product", as_index=False).agg(Revenue=("Total", "sum"), Units=("Qty", "sum"))
            chart = alt.Chart(g).mark_bar(cornerRadiusEnd=4, color=BLUE, height={"band": 0.6}).encode(
                y=alt.Y("Product:N", sort="-x", title=None), x=alt.X("Revenue:Q", title="Rs"),
                tooltip=["Product", alt.Tooltip("Revenue:Q", format=",.2f"), "Units"])
            st.altair_chart(chart_style(chart.properties(height=max(150, 36 * len(g)))), width="stretch",
                            theme=None)
        with c2, st.container(border=True):
            st.markdown("**Cumulative revenue**")
            cum = view.sort_values("Sale ID").assign(Cumulative=lambda d: d["Total"].cumsum())
            line = alt.Chart(cum).mark_line(color=BLUE, strokeWidth=2, point=alt.OverlayMarkDef(size=60)).encode(
                x=alt.X("Sale ID:O", title="Sale #"), y=alt.Y("Cumulative:Q", title="Rs"),
                tooltip=["Sale ID", "Date/Time", "Product", alt.Tooltip("Total:Q", format=",.2f"),
                         alt.Tooltip("Cumulative:Q", format=",.2f")])
            st.altair_chart(chart_style(line.properties(height=max(150, 36 * min(len(g), 10)))),
                            width="stretch", theme=None)

    st.dataframe(view.drop(columns=["Date"]).iloc[::-1], hide_index=True, width="stretch",
                 column_config={"Unit price": st.column_config.NumberColumn(format="Rs %.2f"),
                                "Total": st.column_config.NumberColumn(format="Rs %.2f")})
    st.download_button("Export CSV", view.to_csv(index=False), "sales.csv", icon=":material/download:")


# ---------------------------------------------------------------------------
# Page: Undo & system
# ---------------------------------------------------------------------------
def do_undo() -> None:
    system = get_system()
    try:
        msg = system.undo()
        flash(msg)
        log("↩️", msg)
    except InventoryError as exc:
        flash(str(exc), "warning")
    except OSError as exc:
        flash(f"File error during undo: {exc}", "error")


def do_save() -> None:
    try:
        get_system().save_all()
        flash("All data saved.")
        log("💾", "Saved products.txt and restock.txt")
    except OSError as exc:
        flash(f"Could not save: {exc}", "error")


def do_reload() -> None:
    system = get_system()
    system.initialize()
    system.clear_undo()
    st.session_state.cart = {}
    flash("Data reloaded from the text files (undo history cleared).", "info")
    for w in system.fm.warnings:
        flash(w, "warning")


def page_system() -> None:
    system = get_system()
    page_header("⚙️", "Undo & System", "LIFO undo stack, file storage and project information")
    t1, t2, t3 = st.tabs([":material/undo: Undo stack", ":material/description: Data files",
                          ":material/school: About the project"])
    with t1:
        st.caption("Supported: **add, update, delete product** and **sell product**. The most recent "
                   "operation (top of the stack) is undone first. Receiving restock or applying discounts "
                   "clears the stack. The stack is not saved between runs.")
        c1, c2 = st.columns([2, 1])
        with c1:
            if not system.undo_stack:
                st.info("The undo stack is empty – nothing to undo.", icon="📭")
            else:
                items = []
                for i, rec in enumerate(reversed(system.undo_stack)):
                    icon = {UndoType.ADD_PRODUCT.value: "➕", UndoType.DELETE_PRODUCT.value: "🗑️",
                            UndoType.UPDATE_PRODUCT.value: "✏️",
                            UndoType.SELL_PRODUCT.value: "💰"}.get(rec.type.value, "•")
                    top = "top" if i == 0 else ""
                    label = "TOP → " if i == 0 else ""
                    items.append(f'<div class="node {top}">{label}{icon} {html.escape(rec.describe())}'
                                 f'<small>{rec.when}</small></div>')
                st.markdown(f'<div class="stack">{"".join(items)}<div class="chip" style="width:fit-content">'
                            f'bottom</div></div>', unsafe_allow_html=True)
        with c2:
            st.metric("Stack depth", len(system.undo_stack), border=True)
            st.button("Undo last operation", type="primary", icon=":material/undo:", width="stretch",
                      disabled=not system.undo_stack, on_click=do_undo)
            st.button("Save all data", icon=":material/save:", width="stretch", on_click=do_save)
            st.button("Reload from files", icon=":material/refresh:", width="stretch", on_click=do_reload,
                      help="Use after editing the .txt files or running the C++ program")

    with t2:
        st.caption(f"Data folder: `{DATA_FOLDER}` – shared with the C++ console program. Changes are saved "
                   "immediately (written to a .tmp file first, then swapped in).")
        for label, path in (("products.txt", system.fm.products_path), ("sales.txt", system.fm.sales_path),
                            ("restock.txt", system.fm.restock_path)):
            with st.expander(label, icon=":material/article:"):
                try:
                    with open(path, encoding="utf-8") as f:
                        content = f.read()
                except OSError as exc:
                    content = f"(cannot read: {exc})"
                st.code(content, language=None)
                st.download_button(f"Download {label}", content, label, key=f"dl_{label}",
                                   icon=":material/download:")

    with t3:
        st.markdown(f"""
**Store Inventory and Optimization System** – a menu-driven C++17 application with this Streamlit
web interface on top. Both use the same business rules and the same text files.

| Concept | Where it is used |
|---|---|
| Singly linked list | `Product` nodes in `ProductManager` – the shared product collection |
| Sorting | index of `(id, pointer)` sorted by ID – *O(n log n)* |
| Binary search | `findProductById` on the sorted index – *O(log n)* (see **Products → Binary search lab**) |
| Queue (FIFO) | restock requests – oldest received first (see **Inventory → Restock queue**) |
| Stack (LIFO) | undo of add / update / delete / sale (see the **Undo stack** tab) |
| File handling | `products.txt`, `sales.txt`, `restock.txt` with safe `.tmp` writes and `.bak` backups |
| OOP | `FileManager`, `ProductManager`, `SalesManager`, `InventoryManager`, `SystemManager` |

**Business rules:** low stock when quantity ≤ reorder level · target stock = {TARGET_STOCK_MULTIPLIER} × reorder
level · near expiry = 0–{NEAR_EXPIRY_DAYS} days · discount = {DISCOUNT_PERCENT}% · sales billed at the discounted price.

**Architecture**
```
Streamlit UI (app.py) ─┐
                       ├─> inventory_core.py (Python port) ─┐
C++ console (main.cpp) ─> SystemManager → Product/Sales/Inventory managers ─┴─> FileManager → *.txt
```
""")


# ---------------------------------------------------------------------------
# Main: navigation + sidebar
# ---------------------------------------------------------------------------
def main() -> None:
    system = get_system()
    if system.files_changed_externally():
        do_reload()
        flash("The data files were changed outside the app – reloaded the latest data.", "info")

    pages = {
        "Overview": [st.Page(page_dashboard, title="Dashboard", icon=":material/dashboard:", default=True)],
        "Store": [
            st.Page(page_products, title="Products", icon=":material/inventory_2:", url_path="products"),
            st.Page(page_pos, title="Point of Sale", icon=":material/point_of_sale:", url_path="pos"),
            st.Page(page_sales, title="Sales History", icon=":material/receipt_long:", url_path="sales"),
        ],
        "Stock control": [
            st.Page(page_inventory, title="Inventory & Restock", icon=":material/local_shipping:",
                    url_path="inventory"),
            st.Page(page_expiry, title="Expiry & Discounts", icon=":material/event_busy:", url_path="expiry"),
        ],
        "System": [st.Page(page_system, title="Undo & System", icon=":material/settings_backup_restore:",
                           url_path="system")],
    }
    nav = st.navigation(pages)

    with st.sidebar:
        st.markdown("### 🏪 Store Inventory")
        low = len(system.inventory.low_stock())
        cart_items = sum(st.session_state.cart.values())
        st.markdown(
            f'<div class="side-stat"><span>📦 Products</span><b>{system.products.count}</b></div>'
            f'<div class="side-stat"><span>📉 Low stock</span><b>{low}</b></div>'
            f'<div class="side-stat"><span>🚚 Restock queue</span><b>{len(system.inventory.pending)}</b></div>'
            f'<div class="side-stat"><span>🧺 Cart items</span><b>{cart_items}</b></div>'
            f'<div class="side-stat"><span>↩️ Undo stack</span><b>{len(system.undo_stack)}</b></div>',
            unsafe_allow_html=True,
        )
        st.write("")
        c1, c2 = st.columns(2)
        c1.button("Undo", icon=":material/undo:", width="stretch", disabled=not system.undo_stack,
                  on_click=do_undo, help=system.undo_stack[-1].describe() if system.undo_stack else None)
        c2.button("Save", icon=":material/save:", width="stretch", on_click=do_save)
        st.caption(f"Data: products.txt · sales.txt · restock.txt\n\nToday: {system_date()}")

    nav.run()
    show_flashes()


main()
