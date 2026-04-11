import streamlit as st
import pandas as pd
import psycopg2
import psycopg2.extras
from datetime import datetime, date
import numpy as np

# =============== DATABASE CONNECTION ===============

def get_conn():
    db_url = st.secrets["database"]["url"]
    return psycopg2.connect(db_url, sslmode="require")

def init_db():
    with get_conn() as conn:
        with conn.cursor() as cur:

            cur.execute("""
                CREATE TABLE IF NOT EXISTS items (
                    id SERIAL PRIMARY KEY,
                    sku TEXT UNIQUE, name TEXT NOT NULL, category TEXT,
                    clay_body TEXT, glaze TEXT, size TEXT, price REAL DEFAULT 0,
                    qty_on_hand REAL DEFAULT 0, location TEXT, notes TEXT,
                    image_path TEXT, created_at TEXT, updated_at TEXT
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS stock_moves (
                    id SERIAL PRIMARY KEY, item_id INTEGER NOT NULL,
                    move_type TEXT NOT NULL, quantity REAL NOT NULL,
                    reference TEXT, moved_at TEXT,
                    FOREIGN KEY(item_id) REFERENCES items(id)
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id SERIAL PRIMARY KEY, name TEXT NOT NULL,
                    event_date TEXT NOT NULL, location TEXT, event_type TEXT,
                    theme TEXT, theme_description TEXT, change_goal TEXT,
                    color_palette TEXT, target_customer TEXT, price_strategy TEXT,
                    booth_fee REAL DEFAULT 0, setup_time TEXT, weather TEXT,
                    foot_traffic TEXT, total_revenue REAL DEFAULT 0,
                    cash_sales REAL DEFAULT 0, card_sales REAL DEFAULT 0,
                    check_sales REAL DEFAULT 0, discounts_given REAL DEFAULT 0,
                    rewards_given REAL DEFAULT 0, status TEXT DEFAULT 'planned',
                    created_at TEXT, updated_at TEXT
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS event_inventory (
                    id SERIAL PRIMARY KEY, event_id INTEGER NOT NULL,
                    item_sku TEXT NOT NULL, item_name TEXT NOT NULL,
                    quantity_brought INTEGER DEFAULT 0, quantity_sold INTEGER DEFAULT 0,
                    price_at_event REAL DEFAULT 0,
                    UNIQUE(event_id, item_sku),
                    FOREIGN KEY(event_id) REFERENCES events(id)
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS event_reflections (
                    id SERIAL PRIMARY KEY, event_id INTEGER NOT NULL,
                    category TEXT NOT NULL, content TEXT NOT NULL,
                    customer_interaction INTEGER DEFAULT 0,
                    price_point_insight INTEGER DEFAULT 0,
                    created_at TEXT,
                    FOREIGN KEY(event_id) REFERENCES events(id)
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS event_environment (
                    id SERIAL PRIMARY KEY, event_id INTEGER NOT NULL UNIQUE,
                    neighboring_vendor_left TEXT, neighboring_vendor_right TEXT,
                    booth_location TEXT, foot_traffic_pattern TEXT,
                    customer_demographics TEXT, competition_notes TEXT,
                    pricing_observations TEXT, created_at TEXT,
                    FOREIGN KEY(event_id) REFERENCES events(id)
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS business_goals (
                    id SERIAL PRIMARY KEY, goal_name TEXT NOT NULL,
                    goal_type TEXT NOT NULL, target_value REAL NOT NULL,
                    target_date TEXT NOT NULL, current_value REAL DEFAULT 0,
                    measurement_unit TEXT, category TEXT, description TEXT,
                    status TEXT DEFAULT 'active', created_at TEXT, updated_at TEXT
                )
            """)

        conn.commit()

# =============== HELPER FUNCTIONS ===============

def safe_string(value, default=""):
    if value is None:
        return default
    try:
        return str(value).replace('\x00', '').strip()
    except:
        return default

def safe_float(value, default=0.0):
    try:
        return float(value or 0)
    except:
        return default

def safe_int(value, default=0):
    try:
        return int(value or 0)
    except:
        return default

def rows_to_df(cur):
    if cur.description is None:
        return pd.DataFrame()
    cols = [c[0] for c in cur.description]
    return pd.DataFrame(cur.fetchall(), columns=cols)

# =============== DATA FUNCTIONS ===============

def upsert_item(row: dict):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                now = datetime.utcnow().isoformat()
                cur.execute("""
                    INSERT INTO items (sku, name, category, clay_body, glaze, size, price,
                                      qty_on_hand, location, notes, image_path, created_at, updated_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT(sku) DO UPDATE SET
                        name=EXCLUDED.name, category=EXCLUDED.category,
                        clay_body=EXCLUDED.clay_body, glaze=EXCLUDED.glaze,
                        size=EXCLUDED.size, price=EXCLUDED.price,
                        qty_on_hand=EXCLUDED.qty_on_hand, location=EXCLUDED.location,
                        notes=EXCLUDED.notes, image_path=EXCLUDED.image_path, updated_at=%s
                """, (safe_string(row.get("sku")), safe_string(row.get("name")),
                      safe_string(row.get("category")), safe_string(row.get("clay_body")),
                      safe_string(row.get("glaze")), safe_string(row.get("size")),
                      safe_float(row.get("price")), safe_float(row.get("qty_on_hand")),
                      safe_string(row.get("location")), safe_string(row.get("notes")),
                      safe_string(row.get("image_path")), now, now, now))
            conn.commit()
    except Exception as e:
        st.error(f"Error saving item: {e}")

def fetch_items_df(search: str = "") -> pd.DataFrame:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                if search:
                    q = f"%{safe_string(search).strip()}%"
                    cur.execute("""
                        SELECT * FROM items
                        WHERE name ILIKE %s OR sku ILIKE %s OR category ILIKE %s
                           OR glaze ILIKE %s OR clay_body ILIKE %s
                        ORDER BY COALESCE(updated_at, created_at) DESC
                    """, (q, q, q, q, q))
                else:
                    cur.execute("SELECT * FROM items ORDER BY COALESCE(updated_at, created_at) DESC")
                return rows_to_df(cur)
    except Exception as e:
        st.error(f"Database error: {e}")
        return pd.DataFrame()

def delete_item(item_id):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM stock_moves WHERE item_id = %s", (item_id,))
                cur.execute("DELETE FROM items WHERE id = %s", (item_id,))
            conn.commit()
    except Exception as e:
        st.error(f"Error deleting item: {e}")

def record_move(item_id: int, move_type: str, quantity: float, reference: str = ""):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                now = datetime.utcnow().isoformat()
                cur.execute("""
                    INSERT INTO stock_moves (item_id, move_type, quantity, reference, moved_at)
                    VALUES (%s,%s,%s,%s,%s)
                """, (safe_int(item_id), safe_string(move_type),
                      safe_float(quantity), safe_string(reference), now))
                cur.execute("""
                    UPDATE items SET qty_on_hand = qty_on_hand + %s, updated_at = %s WHERE id = %s
                """, (safe_float(quantity), now, safe_int(item_id)))
            conn.commit()
    except Exception as e:
        st.error(f"Error recording move: {e}")

def create_event(event_data):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                now = datetime.utcnow().isoformat()
                cur.execute("""
                    INSERT INTO events (name, event_date, location, event_type, theme,
                        theme_description, change_goal, color_palette, target_customer,
                        price_strategy, booth_fee, setup_time, weather, foot_traffic,
                        total_revenue, cash_sales, card_sales, check_sales,
                        discounts_given, rewards_given, status, created_at, updated_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    RETURNING id
                """, (safe_string(event_data.get("name")), str(event_data.get("event_date", "")),
                      safe_string(event_data.get("location")), safe_string(event_data.get("event_type")),
                      safe_string(event_data.get("theme")), safe_string(event_data.get("theme_description")),
                      safe_string(event_data.get("change_goal")), safe_string(event_data.get("color_palette")),
                      safe_string(event_data.get("target_customer")), safe_string(event_data.get("price_strategy")),
                      safe_float(event_data.get("booth_fee")), safe_string(event_data.get("setup_time")),
                      safe_string(event_data.get("weather")), safe_string(event_data.get("foot_traffic")),
                      safe_float(event_data.get("total_revenue")), safe_float(event_data.get("cash_sales")),
                      safe_float(event_data.get("card_sales")), safe_float(event_data.get("check_sales")),
                      safe_float(event_data.get("discounts_given")), safe_float(event_data.get("rewards_given")),
                      safe_string(event_data.get("status", "planned")), now, now))
                event_id = cur.fetchone()[0]
            conn.commit()
            return event_id
    except Exception as e:
        st.error(f"Error creating event: {e}")
        return None

def update_event(event_id, event_data):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                now = datetime.utcnow().isoformat()
                cur.execute("""
                    UPDATE events SET
                        name=%s, event_date=%s, location=%s, event_type=%s, theme=%s,
                        theme_description=%s, change_goal=%s, color_palette=%s,
                        target_customer=%s, price_strategy=%s, booth_fee=%s, setup_time=%s,
                        weather=%s, foot_traffic=%s, total_revenue=%s, cash_sales=%s,
                        card_sales=%s, check_sales=%s, discounts_given=%s, rewards_given=%s,
                        status=%s, updated_at=%s
                    WHERE id=%s
                """, (safe_string(event_data.get("name")), str(event_data.get("event_date", "")),
                      safe_string(event_data.get("location")), safe_string(event_data.get("event_type")),
                      safe_string(event_data.get("theme")), safe_string(event_data.get("theme_description")),
                      safe_string(event_data.get("change_goal")), safe_string(event_data.get("color_palette")),
                      safe_string(event_data.get("target_customer")), safe_string(event_data.get("price_strategy")),
                      safe_float(event_data.get("booth_fee")), safe_string(event_data.get("setup_time")),
                      safe_string(event_data.get("weather")), safe_string(event_data.get("foot_traffic")),
                      safe_float(event_data.get("total_revenue")), safe_float(event_data.get("cash_sales")),
                      safe_float(event_data.get("card_sales")), safe_float(event_data.get("check_sales")),
                      safe_float(event_data.get("discounts_given")), safe_float(event_data.get("rewards_given")),
                      safe_string(event_data.get("status", "planned")), now, safe_int(event_id)))
            conn.commit()
            return True
    except Exception as e:
        st.error(f"Error updating event: {e}")
        return False

def get_events():
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM events ORDER BY event_date DESC")
                return rows_to_df(cur)
    except Exception as e:
        st.error(f"Error loading events: {e}")
        return pd.DataFrame()

def get_event_by_id(event_id: int):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM events WHERE id = %s", (safe_int(event_id),))
                row = cur.fetchone()
                if not row:
                    return None
                cols = [c[0] for c in cur.description]
                return dict(zip(cols, row))
    except Exception as e:
        st.error(f"Error loading event: {e}")
        return None

def delete_event(event_id):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM events WHERE id = %s", (event_id,))
                if cur.fetchone()[0] == 0:
                    st.error(f"Event with ID {event_id} not found")
                    return False
                cur.execute("DELETE FROM event_inventory WHERE event_id = %s", (event_id,))
                inv_count = cur.rowcount
                cur.execute("DELETE FROM event_reflections WHERE event_id = %s", (event_id,))
                ref_count = cur.rowcount
                cur.execute("DELETE FROM event_environment WHERE event_id = %s", (event_id,))
                env_count = cur.rowcount
                cur.execute("DELETE FROM events WHERE id = %s", (event_id,))
                evt_count = cur.rowcount
            conn.commit()
            st.info(f"Deleted: {evt_count} event, {inv_count} inventory items, {ref_count} reflections, {env_count} environment records")
            return evt_count > 0
    except Exception as e:
        st.error(f"Error deleting event: {e}")
        return False

def add_event_inventory(event_id, sku, name, brought, sold, price):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO event_inventory
                        (event_id, item_sku, item_name, quantity_brought, quantity_sold, price_at_event)
                    VALUES (%s,%s,%s,%s,%s,%s)
                    ON CONFLICT(event_id, item_sku) DO UPDATE SET
                        item_name=EXCLUDED.item_name,
                        quantity_brought=EXCLUDED.quantity_brought,
                        quantity_sold=EXCLUDED.quantity_sold,
                        price_at_event=EXCLUDED.price_at_event
                """, (safe_int(event_id), safe_string(sku), safe_string(name),
                      safe_int(brought), safe_int(sold), safe_float(price)))
            conn.commit()
    except Exception as e:
        st.error(f"Error adding event inventory: {e}")

def get_event_inventory(event_id):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM event_inventory WHERE event_id = %s", (safe_int(event_id),))
                return rows_to_df(cur)
    except Exception as e:
        st.error(f"Error loading event inventory: {e}")
        return pd.DataFrame()

def delete_event_inventory_row(inventory_id):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM event_inventory WHERE id = %s", (inventory_id,))
            conn.commit()
    except Exception as e:
        st.error(f"Error deleting inventory row: {e}")

def add_reflection(event_id, category, content, customer_interaction=False, price_point_insight=False):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                now = datetime.utcnow().isoformat()
                cur.execute("""
                    INSERT INTO event_reflections
                        (event_id, category, content, customer_interaction, price_point_insight, created_at)
                    VALUES (%s,%s,%s,%s,%s,%s)
                """, (safe_int(event_id), safe_string(category), safe_string(content),
                      int(bool(customer_interaction)), int(bool(price_point_insight)), now))
            conn.commit()
    except Exception as e:
        st.error(f"Error adding reflection: {e}")

def get_reflections(event_id=None):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                if event_id:
                    cur.execute("""
                        SELECT * FROM event_reflections WHERE event_id = %s ORDER BY created_at DESC
                    """, (safe_int(event_id),))
                else:
                    cur.execute("""
                        SELECT er.*, e.name as event_name, e.event_date
                        FROM event_reflections er
                        JOIN events e ON er.event_id = e.id
                        ORDER BY er.created_at DESC
                    """)
                return rows_to_df(cur)
    except Exception as e:
        st.error(f"Error loading reflections: {e}")
        return pd.DataFrame()

def delete_reflection(reflection_id):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM event_reflections WHERE id = %s", (reflection_id,))
            conn.commit()
    except Exception as e:
        st.error(f"Error deleting reflection: {e}")

def add_environment_data(event_id, environment_data):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                now = datetime.utcnow().isoformat()
                cur.execute("""
                    INSERT INTO event_environment
                        (event_id, neighboring_vendor_left, neighboring_vendor_right, booth_location,
                         foot_traffic_pattern, customer_demographics, competition_notes,
                         pricing_observations, created_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT(event_id) DO UPDATE SET
                        neighboring_vendor_left=EXCLUDED.neighboring_vendor_left,
                        neighboring_vendor_right=EXCLUDED.neighboring_vendor_right,
                        booth_location=EXCLUDED.booth_location,
                        foot_traffic_pattern=EXCLUDED.foot_traffic_pattern,
                        customer_demographics=EXCLUDED.customer_demographics,
                        competition_notes=EXCLUDED.competition_notes,
                        pricing_observations=EXCLUDED.pricing_observations
                """, (safe_int(event_id),
                      safe_string(environment_data.get("neighboring_vendor_left")),
                      safe_string(environment_data.get("neighboring_vendor_right")),
                      safe_string(environment_data.get("booth_location")),
                      safe_string(environment_data.get("foot_traffic_pattern")),
                      safe_string(environment_data.get("customer_demographics")),
                      safe_string(environment_data.get("competition_notes")),
                      safe_string(environment_data.get("pricing_observations")), now))
            conn.commit()
    except Exception as e:
        st.error(f"Error adding environment data: {e}")

def get_environment_data(event_id):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM event_environment WHERE event_id = %s", (safe_int(event_id),))
                row = cur.fetchone()
                if not row:
                    return None
                cols = [c[0] for c in cur.description]
                return dict(zip(cols, row))
    except Exception as e:
        st.error(f"Error loading environment data: {e}")
        return None

def get_business_insights():
    insights = {}
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    SELECT
                        CASE
                            WHEN price_at_event < 20 THEN 'Under $20'
                            WHEN price_at_event < 30 THEN '$20-30'
                            WHEN price_at_event < 40 THEN '$30-40'
                            WHEN price_at_event < 50 THEN '$40-50'
                            WHEN price_at_event < 75 THEN '$50-75'
                            ELSE '$75+'
                        END as price_range,
                        COUNT(*) as items_in_range,
                        SUM(quantity_sold) as total_sold,
                        AVG(quantity_sold * 1.0 / NULLIF(quantity_brought, 0)) as avg_sell_through_rate,
                        SUM(quantity_sold * price_at_event) as total_revenue
                    FROM event_inventory
                    WHERE quantity_brought > 0
                    GROUP BY 1
                    ORDER BY avg_sell_through_rate DESC
                """)
                insights['price_analysis'] = rows_to_df(cur)

                cur.execute("""
                    SELECT
                        ei.item_name,
                        COUNT(DISTINCT ei.event_id) as events_brought_to,
                        SUM(ei.quantity_brought) as total_brought,
                        SUM(ei.quantity_sold) as total_sold,
                        AVG(ei.quantity_sold * 1.0 / NULLIF(ei.quantity_brought, 0)) as avg_sell_through_rate,
                        SUM(ei.quantity_sold * ei.price_at_event) as total_revenue,
                        CASE
                            WHEN AVG(ei.quantity_sold * 1.0 / NULLIF(ei.quantity_brought, 0)) > 0.8 THEN 'MAKE MORE'
                            WHEN AVG(ei.quantity_sold * 1.0 / NULLIF(ei.quantity_brought, 0)) > 0.5 THEN 'GOOD'
                            WHEN AVG(ei.quantity_sold * 1.0 / NULLIF(ei.quantity_brought, 0)) > 0.2 THEN 'REVIEW'
                            ELSE 'MAKE LESS'
                        END as recommendation
                    FROM event_inventory ei
                    WHERE ei.quantity_brought > 0
                    GROUP BY ei.item_name
                    HAVING COUNT(DISTINCT ei.event_id) >= 2
                    ORDER BY avg_sell_through_rate DESC
                """)
                insights['make_more_less'] = rows_to_df(cur)

                cur.execute("""
                    SELECT
                        CASE
                            WHEN EXTRACT(MONTH FROM TO_DATE(e.event_date, 'YYYY-MM-DD')) IN (12,1,2) THEN 'Winter'
                            WHEN EXTRACT(MONTH FROM TO_DATE(e.event_date, 'YYYY-MM-DD')) IN (3,4,5) THEN 'Spring'
                            WHEN EXTRACT(MONTH FROM TO_DATE(e.event_date, 'YYYY-MM-DD')) IN (6,7,8) THEN 'Summer'
                            ELSE 'Fall'
                        END as season,
                        ei.item_name,
                        SUM(ei.quantity_sold) as total_sold,
                        AVG(ei.price_at_event) as avg_price,
                        AVG(ei.quantity_sold * 1.0 / NULLIF(ei.quantity_brought, 0)) as avg_sell_through_rate
                    FROM event_inventory ei
                    JOIN events e ON ei.event_id = e.id
                    WHERE e.status = 'completed' AND ei.quantity_brought > 0
                    GROUP BY season, ei.item_name
                    HAVING SUM(ei.quantity_sold) > 0
                    ORDER BY season, total_sold DESC
                """)
                insights['seasonal_analysis'] = rows_to_df(cur)

                cur.execute("""
                    SELECT event_type,
                           COUNT(*) as total_events,
                           AVG(total_revenue) as avg_revenue,
                           AVG(total_revenue - booth_fee) as avg_profit,
                           AVG(CASE WHEN booth_fee > 0 THEN total_revenue / booth_fee ELSE NULL END) as avg_roi
                    FROM events
                    WHERE status = 'completed'
                    GROUP BY event_type
                    ORDER BY avg_revenue DESC
                """)
                insights['event_performance'] = rows_to_df(cur)

    except Exception as e:
        st.error(f"Error generating insights: {e}")
    return insights

# =============== UI SECTIONS ===============

def about_section():
    st.header("About Maker Strategy Pro")
    st.markdown("""
    ### Strategic Planning for Creative Entrepreneurs

    Maker Strategy Pro was designed by:

    Alford Wayman of Creek Road Pottery LLC
    917 Creek Road Laceyville, PA 18623
    www.creekroadpottery.com

    Maker Strategy Pro was designed specifically for artists, craftspeople, and creative entrepreneurs who want to grow their business strategically while staying true to their artistic vision.

    **The Core Philosophy:**

    At the heart of Maker Strategy Pro is one fundamental question: **"What change are you trying to make?"**

    **Key Features:**

    🎯 **Strategic Event Planning** - Plan events with intention, focusing on your change goals rather than just revenue

    📊 **Business Insights Dashboard** - Data-driven recommendations for what to make more/less of, optimal pricing, and seasonal trends

    📝 **Event Reflection Journal** - Capture learnings from each event to continuously improve your approach

    📦 **Inventory Management** - Track your pieces and understand what sells best where

    ---

    **Built for artists, by artists.** Focus on your craft, grow your business.
    """)

def help_section():
    st.header("Help & User Guide")
    st.markdown("### Getting Started")

    with st.expander("Quick Start Guide", expanded=True):
        st.markdown("""
        **1. Plan Your First Event** - Go to "Strategic Event Planning", answer "What change are you trying to make?", and save.

        **2. Add Your Inventory** - Go to "Inventory Management" and add your pieces with SKUs and pricing.

        **3. Track Event Performance** - Go to "Event Management", add inventory items, record what sold.

        **4. Reflect and Learn** - Go to "Event Reflection Journal" and capture insights while fresh.

        **5. Use Insights to Improve** - Go to "Business Insights" for make more/less recommendations.
        """)

    with st.expander("Business Insights - How to Read Recommendations"):
        st.markdown("""
        - **MAKE MORE:** >80% sell-through rate — high demand
        - **GOOD:** 50-80% sell-through rate — solid performers
        - **REVIEW:** 20-50% sell-through rate — consider modifications
        - **MAKE LESS:** <20% sell-through rate — low demand

        You need at least **2 completed events** with inventory data for insights to appear.
        """)

    with st.expander("Common Issues"):
        st.markdown("""
        **Insights Show No Data:** You need at least 2 events with inventory tracking, marked as "completed."

        **Sell-Through Rates Seem Wrong:** Verify quantities brought vs. sold. Rate = Sold ÷ Brought.
        """)

    st.info("This tool supports your artistic journey — use insights to make informed decisions, but always stay true to your vision.")

# =============== UI COMPONENTS ===============

def strategic_event_planning():
    st.header("Strategic Event Planning")
    st.markdown("*Plan your creative vision and business strategy*")

    events_df = get_events()
    edit_mode = False
    existing_event = None

    if not events_df.empty:
        with st.expander("Edit Existing Event", expanded=False):
            event_options = ["Create New Event"] + [f"{row['name']} - {row['event_date']}" for _, row in events_df.iterrows()]
            selected_option = st.selectbox("Select Event", event_options)
            if selected_option != "Create New Event":
                edit_mode = True
                event_idx = event_options.index(selected_option) - 1
                existing_event = events_df.iloc[event_idx]
                st.info(f"Editing: {existing_event['name']}")

    default_name = existing_event['name'] if edit_mode else ""
    default_date = pd.to_datetime(existing_event['event_date']).date() if edit_mode else date.today()
    default_location = existing_event['location'] if edit_mode else ""
    default_event_type = existing_event['event_type'] if edit_mode else "Art Fair"
    default_booth_fee = float(existing_event['booth_fee']) if edit_mode else 0.0
    default_setup_time = existing_event['setup_time'] if edit_mode else ""
    default_theme_name = existing_event['theme'] if edit_mode else ""
    default_theme_desc = existing_event['theme_description'] if edit_mode else ""
    default_change_goal = existing_event['change_goal'] if edit_mode else ""
    default_color_palette = existing_event['color_palette'] if edit_mode else ""
    default_target_customer = existing_event['target_customer'] if edit_mode else ""
    default_price_strategy = existing_event['price_strategy'] if edit_mode else ""
    default_weather = existing_event['weather'] if edit_mode else ""
    default_foot_traffic = existing_event['foot_traffic'] if edit_mode and existing_event['foot_traffic'] else "Moderate"
    default_total_revenue = float(existing_event['total_revenue']) if edit_mode else 0.0
    default_cash_sales = float(existing_event['cash_sales']) if edit_mode else 0.0
    default_card_sales = float(existing_event['card_sales']) if edit_mode else 0.0
    default_status = existing_event['status'] if edit_mode else "planned"

    st.subheader("Event Information")
    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input("Event Name", value=default_name)
        event_date = st.date_input("Event Date", value=default_date)
        location = st.text_input("Location", value=default_location)
        event_type_options = ["Art Fair", "Farmers Market", "Studio Sale", "Gallery Show",
                              "Holiday Market", "Pop-up Shop", "Commission Show", "Online Sale", "Other"]
        event_type_idx = event_type_options.index(default_event_type) if default_event_type in event_type_options else 0
        event_type = st.selectbox("Event Type", event_type_options, index=event_type_idx)
    with col2:
        booth_fee = st.number_input("Booth Fee ($)", min_value=0.0, step=25.0, value=default_booth_fee)
        setup_time = st.text_input("Setup Time", value=default_setup_time)
        expected_attendance = st.selectbox("Expected Attendance",
            ["Small (< 100)", "Medium (100-500)", "Large (500-1000)", "Very Large (1000+)"])
        revenue_goal = st.number_input("Revenue Goal ($)", min_value=0.0, step=100.0)

    st.subheader("Strategic Intent")
    change_goal = st.text_area("What change are you trying to make?",
                              value=default_change_goal,
                              placeholder="What do you want to achieve with this event? How does it fit your artistic/business growth?",
                              height=100)

    st.subheader("Creative Direction")
    col3, col4 = st.columns(2)
    with col3:
        theme_name = st.text_input("Collection/Theme Name", value=default_theme_name)
        theme_description = st.text_area("Theme Description", value=default_theme_desc,
                                        placeholder="Describe the creative vision, story, or concept...")
        color_palette = st.text_area("Color Palette & Glazes", value=default_color_palette,
                                    placeholder="Specific glazes, color combinations, visual mood...")
    with col4:
        target_customer = st.text_area("Target Customer", value=default_target_customer,
                                      placeholder="Who is your ideal customer for this event?")
        price_strategy = st.text_area("Pricing Strategy", value=default_price_strategy,
                                     placeholder="How will you price for this audience and venue?")
        unique_value = st.text_area("What Makes Your Work Special?",
                                   placeholder="What sets your pottery apart?")

    completed = st.checkbox("Event completed - add results", value=(default_status == "completed"))
    weather_actual = ""
    foot_traffic = "Moderate"
    total_revenue = 0.0
    cash_sales = 0.0
    card_sales = 0.0
    change_achieved = ""

    if completed:
        st.subheader("Event Results")
        col5, col6 = st.columns(2)
        with col5:
            total_revenue = st.number_input("Total Revenue ($)", min_value=0.0, step=0.01, value=default_total_revenue)
            cash_sales = st.number_input("Cash Sales ($)", min_value=0.0, step=0.01, value=default_cash_sales)
            card_sales = st.number_input("Card Sales ($)", min_value=0.0, step=0.01, value=default_card_sales)
        with col6:
            weather_actual = st.text_input("Actual Weather", value=default_weather)
            foot_traffic_options = ["Light", "Moderate", "Heavy", "Excellent"]
            foot_traffic_idx = foot_traffic_options.index(default_foot_traffic) if default_foot_traffic in foot_traffic_options else 1
            foot_traffic = st.selectbox("Foot Traffic", foot_traffic_options, index=foot_traffic_idx)
            change_achieved = st.text_area("Did you achieve the change you were seeking?",
                                         placeholder="Reflect on whether you made progress toward your change goal...")

    button_label = "Update Event" if edit_mode else "Save Event Plan"
    if st.button(button_label, type="primary"):
        if not name:
            st.error("Please enter an event name")
            return None

        event_data = {
            "name": name, "event_date": event_date, "location": location, "event_type": event_type,
            "theme": theme_name, "theme_description": theme_description, "change_goal": change_goal,
            "color_palette": color_palette, "target_customer": target_customer, "price_strategy": price_strategy,
            "booth_fee": booth_fee, "setup_time": setup_time,
            "weather": weather_actual if completed else "",
            "foot_traffic": foot_traffic if completed else "",
            "total_revenue": total_revenue if completed else 0,
            "cash_sales": cash_sales if completed else 0,
            "card_sales": card_sales if completed else 0,
            "check_sales": 0, "discounts_given": 0, "rewards_given": 0,
            "status": "completed" if completed else "planned"
        }

        if edit_mode:
            success = update_event(existing_event['id'], event_data)
            if success:
                st.success(f"Event '{name}' updated successfully!")
                if completed and change_achieved:
                    add_reflection(existing_event['id'], "Change Achievement", change_achieved, False, False)
                st.rerun()
        else:
            event_id = create_event(event_data)
            if event_id:
                st.success(f"Event plan saved successfully (ID: {event_id})")
                if completed and change_achieved:
                    add_reflection(event_id, "Change Achievement", change_achieved, False, False)
                return event_id
    return None

def reflection_journal():
    st.header("Event Reflection Journal")
    st.markdown("*Capture insights and learnings from your events*")

    events_df = get_events()
    if events_df.empty:
        st.info("No events found. Create an event first to start journaling.")
        return

    event_options = [f"{row['name']} - {row['event_date']}" for _, row in events_df.iterrows()]
    selected_event = st.selectbox("Select Event to Reflect On", event_options)

    if selected_event:
        event_idx = event_options.index(selected_event)
        event = events_df.iloc[event_idx]
        event_id = event['id']

        st.subheader(f"Reflecting on: {event['name']}")

        with st.expander("Event Context", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Date:** {event['event_date']}")
                st.write(f"**Location:** {event['location']}")
                st.write(f"**Type:** {event['event_type']}")
                if event['theme']:
                    st.write(f"**Theme:** {event['theme']}")
                if event['change_goal']:
                    st.write(f"**Change Goal:** {event['change_goal']}")
            with col2:
                if event['status'] == 'completed':
                    st.write(f"**Revenue:** ${event['total_revenue']:.2f}")
                    st.write(f"**Booth Fee:** ${event['booth_fee']:.2f}")
                    st.write(f"**Profit:** ${event['total_revenue'] - event['booth_fee']:.2f}")

        st.subheader("Add New Reflection")
        col3, col4 = st.columns(2)
        with col3:
            reflection_category = st.selectbox("Reflection Type", [
                "What Worked Well", "What Didn't Work", "Customer Interactions & Feedback",
                "Pricing Observations", "Display & Setup Insights", "Competition & Market Analysis",
                "Next Time Planning", "Creative Discoveries", "Business Learning", "Change Progress"
            ])
            customer_interaction = st.checkbox("Customer interaction note")
            price_insight = st.checkbox("Contains pricing insights")
        with col4:
            reflection_content = st.text_area("Reflection Content", height=150,
                                            placeholder="What did you observe? What did you learn? How did customers respond?")

        if st.button("Save Reflection") and reflection_content:
            add_reflection(event_id, reflection_category, reflection_content, customer_interaction, price_insight)
            st.success("Reflection saved")
            st.rerun()

        st.subheader("Event Environment")
        env = get_environment_data(event_id)
        with st.expander("Track Event Environment & Context", expanded=False):
            col5, col6 = st.columns(2)
            with col5:
                left_vendor = st.text_input("Left Neighbor", value=safe_string((env or {}).get("neighboring_vendor_left", "")))
                right_vendor = st.text_input("Right Neighbor", value=safe_string((env or {}).get("neighboring_vendor_right", "")))
                booth_location = st.text_input("Booth Location", value=safe_string((env or {}).get("booth_location", "")))
            with col6:
                traffic_pattern = st.text_area("Foot Traffic Pattern", value=safe_string((env or {}).get("foot_traffic_pattern", "")))
                demographics = st.text_area("Customer Demographics", value=safe_string((env or {}).get("customer_demographics", "")))
            competition = st.text_area("Competition Notes", value=safe_string((env or {}).get("competition_notes", "")))
            pricing_obs = st.text_area("Pricing Observations", value=safe_string((env or {}).get("pricing_observations", "")))
            if st.button("Save Environment Data"):
                add_environment_data(event_id, {
                    "neighboring_vendor_left": left_vendor, "neighboring_vendor_right": right_vendor,
                    "booth_location": booth_location, "foot_traffic_pattern": traffic_pattern,
                    "customer_demographics": demographics, "competition_notes": competition,
                    "pricing_observations": pricing_obs
                })
                st.success("Environment data saved")

        reflections = get_reflections(event_id)
        if not reflections.empty:
            st.subheader("Previous Reflections")
            col7, col8, col9 = st.columns(3)
            with col7:
                filter_category = st.selectbox("Filter by Type", ["All"] + list(reflections['category'].unique()))
            with col8:
                show_customer_only = st.checkbox("Customer interactions only")
            with col9:
                show_pricing_only = st.checkbox("Pricing insights only")

            filtered = reflections.copy()
            if filter_category != "All":
                filtered = filtered[filtered['category'] == filter_category]
            if show_customer_only:
                filtered = filtered[filtered['customer_interaction'] == 1]
            if show_pricing_only:
                filtered = filtered[filtered['price_point_insight'] == 1]

            for _, reflection in filtered.iterrows():
                date_str = reflection['created_at'][:10] if reflection['created_at'] else ""
                flags = []
                if reflection['customer_interaction']:
                    flags.append("Customer")
                if reflection['price_point_insight']:
                    flags.append("Pricing")
                title = f"{reflection['category']} - {date_str}"
                if flags:
                    title += f" | {' | '.join(flags)}"
                with st.expander(title):
                    st.write(reflection['content'])

def business_insights_dashboard():
    st.header("Business Insights Dashboard")
    st.markdown("*Data-driven insights for strategic business decisions*")

    insights = get_business_insights()
    if not insights or all(df.empty for df in insights.values()):
        st.info("Complete some events with inventory tracking to see business insights.")
        return

    if 'price_analysis' in insights and not insights['price_analysis'].empty:
        st.subheader("Price Point Performance")
        price_df = insights['price_analysis']
        col1, col2 = st.columns(2)
        with col1:
            st.bar_chart(price_df.set_index('price_range')['avg_sell_through_rate'])
            st.caption("Sell-Through Rate by Price Range")
        with col2:
            best_range = price_df.loc[price_df['avg_sell_through_rate'].idxmax()]
            st.metric("Best Performing Price Range", best_range['price_range'],
                     f"{best_range['avg_sell_through_rate']:.1%} sell-through")
            if best_range['avg_sell_through_rate'] > 0.7:
                st.success(f"Focus more inventory in the {best_range['price_range']} range - strong demand!")
            else:
                st.info(f"Consider experimenting with pricing in the {best_range['price_range']} range")
        st.dataframe(price_df, use_container_width=True)

    if 'make_more_less' in insights and not insights['make_more_less'].empty:
        st.subheader("Production Strategy Recommendations")
        recs_df = insights['make_more_less']
        make_more = recs_df[recs_df['recommendation'] == 'MAKE MORE']
        make_less = recs_df[recs_df['recommendation'] == 'MAKE LESS']
        review = recs_df[recs_df['recommendation'] == 'REVIEW']
        col3, col4, col5 = st.columns(3)
        with col3:
            st.markdown("**MAKE MORE**")
            st.caption("High demand items (>80% sell-through)")
            if not make_more.empty:
                for _, item in make_more.iterrows():
                    st.write(f"• **{item['item_name']}** - {item['avg_sell_through_rate']:.1%}")
            else:
                st.write("No high-demand items yet")
        with col4:
            st.markdown("**REVIEW**")
            st.caption("Moderate performance (20-80% sell-through)")
            if not review.empty:
                for _, item in review.head(3).iterrows():
                    st.write(f"• **{item['item_name']}** - {item['avg_sell_through_rate']:.1%}")
        with col5:
            st.markdown("**MAKE LESS**")
            st.caption("Lower demand items (<20% sell-through)")
            if not make_less.empty:
                for _, item in make_less.iterrows():
                    st.write(f"• **{item['item_name']}** - {item['avg_sell_through_rate']:.1%}")
            else:
                st.write("All items performing well!")
        st.dataframe(recs_df[['item_name', 'events_brought_to', 'avg_sell_through_rate', 'total_revenue', 'recommendation']],
                    use_container_width=True)

    if 'seasonal_analysis' in insights and not insights['seasonal_analysis'].empty:
        st.subheader("Seasonal Performance Trends")
        seasonal_df = insights['seasonal_analysis']
        for season in ['Spring', 'Summer', 'Fall', 'Winter']:
            season_data = seasonal_df[seasonal_df['season'] == season]
            if not season_data.empty:
                with st.expander(f"{season} - Top Items"):
                    for _, item in season_data.head(5).iterrows():
                        st.write(f"• **{item['item_name']}** - {item['total_sold']} sold, ${item['avg_price']:.2f} avg, {item['avg_sell_through_rate']:.1%} sell-through")

    if 'event_performance' in insights and not insights['event_performance'].empty:
        st.subheader("Event Type Performance")
        event_df = insights['event_performance']
        col6, col7 = st.columns(2)
        with col6:
            st.bar_chart(event_df.set_index('event_type')['avg_revenue'])
            st.caption("Average Revenue by Event Type")
        with col7:
            st.bar_chart(event_df.set_index('event_type')['avg_profit'])
            st.caption("Average Profit by Event Type")
        st.dataframe(event_df, use_container_width=True)

def inventory_management():
    st.header("Inventory Management")
    st.markdown("*Track your pottery pieces and stock levels*")

    col1, col2 = st.columns([3, 1])
    with col1:
        search_query = st.text_input("Search inventory", placeholder="Search by name, SKU, category, glaze...")
    with col2:
        if st.button("Add New Item", type="primary"):
            st.session_state['show_item_form'] = True

    if st.session_state.get('show_item_form', False):
        st.subheader("Add New Item")
        col3, col4 = st.columns(2)
        with col3:
            sku = st.text_input("SKU/Code")
            name = st.text_input("Item Name")
            category = st.text_input("Category")
            clay_body = st.text_input("Clay Body")
        with col4:
            glaze = st.text_input("Glaze")
            size = st.text_input("Size")
            price = st.number_input("Price ($)", min_value=0.0, step=1.0)
            qty_on_hand = st.number_input("Quantity on Hand", min_value=0.0, step=1.0)
        location = st.text_input("Location")
        notes = st.text_area("Notes")
        col5, col6 = st.columns(2)
        with col5:
            if st.button("Save Item"):
                if sku and name:
                    upsert_item({"sku": sku, "name": name, "category": category, "clay_body": clay_body,
                                 "glaze": glaze, "size": size, "price": price, "qty_on_hand": qty_on_hand,
                                 "location": location, "notes": notes})
                    st.success("Item saved successfully")
                    st.session_state['show_item_form'] = False
                    st.rerun()
                else:
                    st.error("SKU and Name are required")
        with col6:
            if st.button("Cancel"):
                st.session_state['show_item_form'] = False
                st.rerun()

    items_df = fetch_items_df(search_query)
    if not items_df.empty:
        st.subheader("Current Inventory")
        col7, col8, col9, col10 = st.columns(4)
        with col7:
            st.metric("Total Items", len(items_df))
        with col8:
            st.metric("Total Pieces", int(items_df['qty_on_hand'].sum()))
        with col9:
            st.metric("Total Value", f"${(items_df['qty_on_hand'] * items_df['price']).sum():.2f}")
        with col10:
            st.metric("Low Stock Items", len(items_df[items_df['qty_on_hand'] <= 5]))

        display_cols = ['sku', 'name', 'category', 'clay_body', 'glaze', 'price', 'qty_on_hand', 'location']
        st.dataframe(items_df[display_cols], use_container_width=True)

        st.subheader("Stock Adjustment")
        item_names = [f"{row['sku']} - {row['name']}" for _, row in items_df.iterrows()]
        selected_item = st.selectbox("Select item to adjust", item_names)
        if selected_item:
            item_idx = item_names.index(selected_item)
            item = items_df.iloc[item_idx]
            col11, col12 = st.columns(2)
            with col11:
                quantity_change = st.number_input("Quantity change", value=0.0, step=1.0,
                                                help="Positive to add stock, negative to remove")
            with col12:
                reference = st.text_input("Reference/Reason", placeholder="e.g., 'Completed firing'")
            if st.button("Record Stock Movement") and quantity_change != 0:
                record_move(item['id'], "adjustment", quantity_change, reference)
                st.success("Stock movement recorded")
                st.rerun()
    else:
        st.info("No inventory items found. Add your first item to get started.")

def event_management():
    st.header("Events & Show Management")
    st.markdown("*Manage your events and track what you bring and sell*")

    events_df = get_events()
    if events_df.empty:
        st.info("No events found. Use 'Strategic Event Planning' to create your first event.")
        return

    event_options = [f"{row['name']} - {row['event_date']}" for _, row in events_df.iterrows()]
    selected_event = st.selectbox("Select Event to Manage", event_options)

    if selected_event:
        event_idx = event_options.index(selected_event)
        event = events_df.iloc[event_idx]
        event_id = int(event['id'])

        st.subheader(f"Managing: {event['name']}")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.write(f"**Date:** {event['event_date']}")
            st.write(f"**Location:** {event['location']}")
            st.write(f"**Type:** {event['event_type']}")
        with col2:
            st.write(f"**Status:** {event['status']}")
            if event['booth_fee'] > 0:
                st.write(f"**Booth Fee:** ${event['booth_fee']:.2f}")
        with col3:
            if event['status'] == 'completed':
                st.write(f"**Revenue:** ${event['total_revenue']:.2f}")
                st.write(f"**Profit:** ${event['total_revenue'] - event['booth_fee']:.2f}")

        with st.expander("Danger Zone", expanded=False):
            st.warning("Delete this event and all related data")
            col_del1, col_del2 = st.columns(2)
            with col_del1:
                confirm_delete = st.checkbox("I understand this cannot be undone")
            with col_del2:
                if st.button("Delete Event", type="secondary"):
                    if confirm_delete:
                        if delete_event(event_id):
                            st.success("Event deleted successfully!")
                            st.rerun()
                        else:
                            st.error("Failed to delete event")
                    else:
                        st.error("Please check the confirmation box first")

        st.subheader("Event Inventory")
        items_df = fetch_items_df()
        if not items_df.empty:
            st.markdown("**Add Items to Event:**")
            selected_items = st.multiselect("Select items to add",
                                          options=items_df['sku'].tolist(),
                                          format_func=lambda x: f"{x} - {items_df[items_df['sku']==x]['name'].iloc[0]}")
            if selected_items:
                for sku in selected_items:
                    item = items_df[items_df['sku']==sku].iloc[0]
                    col4, col5, col6, col7 = st.columns(4)
                    with col4:
                        st.write(f"**{item['name']}**")
                    with col5:
                        brought = st.number_input("Brought", min_value=0, key=f"brought_{sku}")
                    with col6:
                        sold = st.number_input("Sold", min_value=0, key=f"sold_{sku}")
                    with col7:
                        price = st.number_input("Price", min_value=0.0, value=float(item['price']), key=f"price_{sku}")
                    if st.button(f"Add {sku} to Event", key=f"add_{sku}"):
                        add_event_inventory(event_id, sku, item['name'], brought, sold, price)
                        st.success(f"Added {item['name']} to event")
                        st.rerun()

        event_inventory = get_event_inventory(event_id)
        if not event_inventory.empty:
            st.markdown("**Current Event Inventory:**")
            event_inventory = event_inventory.copy()
            event_inventory['sell_through_rate'] = (event_inventory['quantity_sold'] /
                                                   event_inventory['quantity_brought'].replace(0, 1)) * 100
            event_inventory['revenue'] = event_inventory['quantity_sold'] * event_inventory['price_at_event']
            st.dataframe(event_inventory, use_container_width=True)

            with st.expander("Delete Inventory Items"):
                for _, row in event_inventory.iterrows():
                    col_item, col_delete = st.columns([3, 1])
                    with col_item:
                        st.write(f"{row['item_name']} - Brought: {row['quantity_brought']}, Sold: {row['quantity_sold']}")
                    with col_delete:
                        if st.button("Delete", key=f"del_inv_{row['id']}"):
                            delete_event_inventory_row(row['id'])
                            st.success("Deleted")
                            st.rerun()

            col8, col9, col10, col11 = st.columns(4)
            with col8:
                st.metric("Total Brought", int(event_inventory['quantity_brought'].sum()))
            with col9:
                st.metric("Total Sold", int(event_inventory['quantity_sold'].sum()))
            with col10:
                overall_sell_through = (event_inventory['quantity_sold'].sum() /
                                      max(event_inventory['quantity_brought'].sum(), 1)) * 100
                st.metric("Overall Sell-Through", f"{overall_sell_through:.1f}%")
            with col11:
                st.metric("Inventory Revenue", f"${event_inventory['revenue'].sum():.2f}")

# =============== MAIN APPLICATION ===============

st.set_page_config(page_title="Maker Strategy Pro", page_icon="🏺", layout="wide")

st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #8B4513, #D2B48C);
        padding: 20px; border-radius: 10px; color: white;
        text-align: center; margin-bottom: 30px;
    }
    .stButton > button {
        background-color: #8B4513; color: white; border-radius: 8px;
        border: none; padding: 12px 24px; font-weight: 500;
    }
    .stButton > button:hover { background-color: #A0522D; }
</style>
""", unsafe_allow_html=True)

try:
    init_db()
except Exception as e:
    st.error(f"Database initialization error: {e}")
    st.stop()

st.markdown("""
<div class="main-header">
    <h1>Maker Strategy Pro</h1>
    <p>Strategic planning and business insights for artists.</p>
</div>
""", unsafe_allow_html=True)

st.sidebar.title("Navigation")
menu_options = [
    "Strategic Event Planning", "Dashboard", "Event Reflection Journal",
    "Business Insights", "Event Management", "Inventory Management", "About", "Help"
]
menu = st.sidebar.selectbox("Go to", menu_options)

if 'show_item_form' not in st.session_state:
    st.session_state['show_item_form'] = False

if menu == "Strategic Event Planning":
    strategic_event_planning()

elif menu == "Dashboard":
    st.header("Overview Dashboard")
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_events,
                        COUNT(CASE WHEN status = 'planned' THEN 1 END) as planned_events,
                        COALESCE(SUM(CASE WHEN status = 'completed' THEN total_revenue ELSE 0 END), 0) as total_revenue,
                        COALESCE(AVG(CASE WHEN status = 'completed' THEN total_revenue ELSE NULL END), 0) as avg_revenue
                    FROM events
                """)
                stats = rows_to_df(cur)
                cur.execute("SELECT COUNT(*) as count FROM items")
                items_count = rows_to_df(cur)

        if not stats.empty:
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric("Items in Inventory", safe_int(items_count.iloc[0]['count']))
            with col2:
                st.metric("Completed Events", safe_int(stats.iloc[0]['completed_events']))
            with col3:
                st.metric("Planned Events", safe_int(stats.iloc[0]['planned_events']))
            with col4:
                st.metric("Total Revenue", f"${safe_float(stats.iloc[0]['total_revenue']):,.2f}")
            with col5:
                st.metric("Avg per Event", f"${safe_float(stats.iloc[0]['avg_revenue']):,.2f}")
    except Exception as e:
        st.error(f"Error loading dashboard: {e}")

    st.subheader("Recent Activity")
    recent_events = get_events().head(5)
    if not recent_events.empty:
        st.markdown("**Recent Events:**")
        for _, event in recent_events.iterrows():
            icon = "✅" if event['status'] == 'completed' else "📅"
            st.write(f"{icon} **{event['name']}** - {event['event_date']} ({event['status']})")

    recent_reflections = get_reflections().head(3)
    if not recent_reflections.empty:
        st.markdown("**Recent Reflections:**")
        for _, reflection in recent_reflections.iterrows():
            with st.expander(f"{reflection['event_name']} - {reflection['category']}"):
                content = reflection['content']
                st.write(content[:200] + "..." if len(content) > 200 else content)

elif menu == "Event Reflection Journal":
    reflection_journal()
elif menu == "Business Insights":
    business_insights_dashboard()
elif menu == "Event Management":
    event_management()
elif menu == "Inventory Management":
    inventory_management()
elif menu == "About":
    about_section()
elif menu == "Help":
    help_section()

st.sidebar.markdown("---")
st.sidebar.markdown("### Maker Strategy Pro")
st.sidebar.markdown("*Strategic planning and business insights for artists*")
st.sidebar.markdown("Focus on your craft, grow your business")    # Recent reflections
    recent_reflections = get_reflections().head(3)
    if not recent_reflections.empty:
        st.markdown("**Recent Reflections:**")
        for _, reflection in recent_reflections.iterrows():
            with st.expander(f"{reflection['event_name']} - {reflection['category']}"):
                st.write(reflection['content'][:200] + "..." if len(reflection['content']) > 200 else reflection['content'])

elif menu == "Event Reflection Journal":
    reflection_journal()

elif menu == "Business Insights":
    business_insights_dashboard()

elif menu == "Event Management":
    event_management()

elif menu == "Inventory Management":
    inventory_management()

elif menu == "About":
    about_section()

elif menu == "Help":
    help_section()

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("### Maker Strategy Pro")
st.sidebar.markdown("*Strategic planning and business insights for artists*")
st.sidebar.markdown("Focus on your craft, grow your business")
