import streamlit as st
import pandas as pd
import sqlite3
from contextlib import closing
from datetime import datetime
from io import BytesIO

DB_PATH = "pottery_shop.db"

# ---------- DB helpers

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sku TEXT UNIQUE,
                name TEXT NOT NULL,
                category TEXT,
                clay_body TEXT,
                glaze TEXT,
                size TEXT,
                price REAL DEFAULT 0,
                qty_on_hand REAL DEFAULT 0,
                location TEXT,
                notes TEXT,
                image_path TEXT,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS stock_moves (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                move_type TEXT NOT NULL,
                quantity REAL NOT NULL,
                reference TEXT,
                moved_at TEXT,
                FOREIGN KEY(item_id) REFERENCES items(id)
            )
            """
        )
        conn.commit()


def upsert_item(row):
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        now = datetime.utcnow().isoformat()
        cur.execute(
            """
            INSERT INTO items (sku, name, category, clay_body, glaze, size, price, qty_on_hand, location, notes, image_path, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(sku) DO UPDATE SET
                name=excluded.name,
                category=excluded.category,
                clay_body=excluded.clay_body,
                glaze=excluded.glaze,
                size=excluded.size,
                price=excluded.price,
                qty_on_hand=excluded.qty_on_hand,
                location=excluded.location,
                notes=excluded.notes,
                image_path=excluded.image_path,
                updated_at=?
            """,
            (
                row.get("sku"),
                row.get("name"),
                row.get("category"),
                row.get("clay_body"),
                row.get("glaze"),
                row.get("size"),
                float(row.get("price", 0) or 0),
                float(row.get("qty_on_hand", 0) or 0),
                row.get("location"),
                row.get("notes"),
                row.get("image_path"),
                now,
                now,
                now,
            ),
        )
        conn.commit()


def fetch_items_df(search=""):
    with closing(get_conn()) as conn:
        if search:
            q = f"%{search.strip()}%"
            df = pd.read_sql_query(
                """
                SELECT * FROM items
                WHERE name LIKE ? OR sku LIKE ? OR category LIKE ? OR glaze LIKE ? OR clay_body LIKE ?
                ORDER BY updated_at DESC NULLS LAST
                """,
                conn,
                params=(q, q, q, q, q),
            )
        else:
            df = pd.read_sql_query("SELECT * FROM items ORDER BY updated_at DESC NULLS LAST", conn)
    return df


def fetch_item_by_sku(sku):
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM items WHERE sku = ?", (sku,))
        row = cur.fetchone()
        if not row:
            return None
        cols = [c[0] for c in cur.description]
        return dict(zip(cols, row))


def record_move(item_id, move_type, quantity, reference=""):
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        now = datetime.utcnow().isoformat()
        cur.execute(
            "INSERT INTO stock_moves (item_id, move_type, quantity, reference, moved_at) VALUES (?, ?, ?, ?, ?)",
            (item_id, move_type, quantity, reference, now),
        )
        cur.execute(
            "UPDATE items SET qty_on_hand = qty_on_hand + ?, updated_at = ? WHERE id = ?",
            (quantity, now, item_id),
        )
        conn.commit()


def delete_item(item_id):
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM stock_moves WHERE item_id = ?", (item_id,))
        cur.execute("DELETE FROM items WHERE id = ?", (item_id,))
        conn.commit()


# ---------- UI helpers

def header(title):
    st.markdown(f"# {title}")


def download_df_button(df, filename):
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV", data=csv, file_name=filename, mime="text/csv")


def upload_csv():
    uploaded = st.file_uploader("Upload CSV to add or update items", type=["csv"])
    if uploaded is not None:
        df = pd.read_csv(uploaded)
        required = {"sku", "name"}
        if not required.issubset(set(df.columns.str.lower())):
            st.error("CSV must include at least sku and name columns")
            return
        df.columns = [c.lower() for c in df.columns]
        count = 0
        for _, r in df.iterrows():
            upsert_item(r)
            count += 1
        st.success(f"Imported or updated {count} rows")


def item_form(existing=None):
    sku = st.text_input("SKU", value=(existing or {}).get("sku", "")).strip()
    name = st.text_input("Name", value=(existing or {}).get("name", "")).strip()
    col1, col2, col3 = st.columns(3)
    with col1:
        category = st.text_input("Category", value=(existing or {}).get("category", ""))
        size = st.text_input("Size", value=(existing or {}).get("size", ""))
        location = st.text_input("Location", value=(existing or {}).get("location", ""))
    with col2:
        clay_body = st.text_input("Clay body", value=(existing or {}).get("clay_body", ""))
        glaze = st.text_input("Glaze", value=(existing or {}).get("glaze", ""))
        price = st.number_input("Price", min_value=0.0, value=float((existing or {}).get("price") or 0.0), step=0.5)
    with col3:
        qty_on_hand = st.number_input("Quantity on hand", min_value=0.0, value=float((existing or {}).get("qty_on_hand") or 0.0), step=1.0)
        image_path = st.text_input("Image path or URL", value=(existing or {}).get("image_path", ""))
        notes = st.text_area("Notes", value=(existing or {}).get("notes", ""))

    if st.button("Save item", type="primary"):
        if not sku or not name:
            st.error("SKU and Name are required")
            return None
        row = {
            "sku": sku,
            "name": name,
            "category": category,
            "clay_body": clay_body,
            "glaze": glaze,
            "size": size,
            "price": price,
            "qty_on_hand": qty_on_hand,
            "location": location,
            "notes": notes,
            "image_path": image_path,
        }
        upsert_item(row)
        st.success("Item saved")
        return sku
    return None


def adjust_stock_ui(item):
    st.subheader("Adjust stock")
    qty = st.number_input("Quantity change", value=0.0, step=1.0)
    ref = st.text_input("Reference or reason")
    if st.button("Record movement"):
        if qty == 0:
            st.warning("Quantity change cannot be zero")
        else:
            record_move(item["id"], "adjustment", qty, ref)
            st.success("Movement recorded")


def movements_table(item_id):
    with closing(get_conn()) as conn:
        mv = pd.read_sql_query(
            "SELECT move_type, quantity, reference, moved_at FROM stock_moves WHERE item_id = ? ORDER BY moved_at DESC",
            conn,
            params=(item_id,),
        )
    st.caption("Recent movements")
    st.dataframe(mv, use_container_width=True)


# ---------- App

st.set_page_config(page_title="Pottery Shop", page_icon="🧱", layout="wide")
init_db()

menu = st.sidebar.selectbox("Go to", ["Dashboard", "Items", "New item", "Import or Export"]) 

if menu == "Dashboard":
    header("Pottery Shop")
    st.write("Simple inventory for potters. Track items and stock movements. Export CSV for bookkeeping.")
    df = fetch_items_df()
    top = df[["sku", "name", "qty_on_hand", "price", "category", "glaze", "updated_at"]].head(25)
    st.subheader("Recent items")
    st.dataframe(top, use_container_width=True)
    download_df_button(df, "pottery_items.csv")

elif menu == "Items":
    header("Items")
    q = st.text_input("Search by name, sku, category, glaze, clay body")
    df = fetch_items_df(q)
    st.dataframe(df, use_container_width=True)

    st.divider()
    sku_pick = st.text_input("Open item by SKU")
    if st.button("Open") and sku_pick:
        item = fetch_item_by_sku(sku_pick)
        if not item:
            st.error("Not found")
        else:
            st.session_state["open_item"] = item

    if "open_item" in st.session_state:
        item = st.session_state["open_item"]
        st.subheader(f"Item {item['sku']}")
        colA, colB = st.columns([1, 2])
        with colA:
            if item.get("image_path"):
                st.image(item["image_path"], caption=item["name"], use_column_width=True)
        with colB:
            st.write(
                {
                    "name": item["name"],
                    "category": item["category"],
                    "clay_body": item["clay_body"],
                    "glaze": item["glaze"],
                    "size": item["size"],
                    "price": item["price"],
                    "qty_on_hand": item["qty_on_hand"],
                    "location": item["location"],
                    "notes": item["notes"],
                }
            )
            adjust_stock_ui(item)
            movements_table(item["id"])

        colD1, colD2 = st.columns(2)
        with colD1:
            if st.button("Edit item"):
                st.session_state["edit_sku"] = item["sku"]
        with colD2:
            if st.button("Delete item"):
                delete_item(item["id"])
                st.success("Item deleted")
                st.session_state.pop("open_item", None)

    if "edit_sku" in st.session_state:
        existing = fetch_item_by_sku(st.session_state["edit_sku"])
        st.subheader("Edit item")
        saved = item_form(existing)
        if saved:
            st.session_state.pop("edit_sku", None)
            st.session_state["open_item"] = fetch_item_by_sku(saved)

elif menu == "New item":
    header("New item")
    saved = item_form()
    if saved:
        st.session_state["open_item"] = fetch_item_by_sku(saved)
        st.experimental_rerun()

elif menu == "Import or Export":
    header("Import or Export")
    st.info("Download a template, fill your rows, then upload the CSV. Existing SKUs will update.")

    template = pd.DataFrame(
        [
            {
                "sku": "MUG12-CRP-RUST",
                "name": "Mug 12 oz Rusty Red",
                "category": "Mug",
                "clay_body": "Stoneware",
                "glaze": "Rusty Red",
                "size": "12 oz",
                "price": 28.0,
                "qty_on_hand": 24,
                "location": "Shelf A",
                "notes": "Gas fired C6",
                "image_path": "",
            }
        ]
    )

    csv_bytes = template.to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV template", data=csv_bytes, file_name="pottery_template.csv", mime="text/csv")

    st.divider()
    upload_csv()

    st.divider()
    with closing(get_conn()) as conn:
        df_all = pd.read_sql_query("SELECT * FROM items ORDER BY updated_at DESC NULLS LAST", conn)
    download_df_button(df_all, "pottery_items_export.csv")

