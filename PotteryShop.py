import streamlit as st
import pandas as pd
import sqlite3
from contextlib import closing
from datetime import datetime, date
from io import BytesIO

DB_PATH = "pottery_shop.db"

# ---------- DB helpers (existing + new tables)

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        
        # Existing tables
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
        
        # New events tables
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                event_date DATE NOT NULL,
                location TEXT,
                event_type TEXT,
                theme TEXT,
                theme_description TEXT,
                color_palette TEXT,
                target_customer TEXT,
                price_strategy TEXT,
                booth_fee REAL DEFAULT 0,
                setup_time TEXT,
                weather TEXT,
                foot_traffic TEXT,
                total_revenue REAL DEFAULT 0,
                cash_sales REAL DEFAULT 0,
                card_sales REAL DEFAULT 0,
                check_sales REAL DEFAULT 0,
                discounts_given REAL DEFAULT 0,
                rewards_given REAL DEFAULT 0,
                status TEXT DEFAULT 'planned',
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        
        # Pre-sale promotion tracking
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS event_promotions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                promotion_type TEXT NOT NULL,
                platform TEXT,
                content TEXT,
                scheduled_date DATE,
                target_audience TEXT,
                engagement_goal TEXT,
                actual_engagement TEXT,
                leads_generated INTEGER DEFAULT 0,
                sales_attributed REAL DEFAULT 0,
                created_at TEXT,
                FOREIGN KEY(event_id) REFERENCES events(id)
            )
            """
        )
        
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS event_inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                item_sku TEXT NOT NULL,
                item_name TEXT NOT NULL,
                quantity_brought INTEGER DEFAULT 0,
                quantity_sold INTEGER DEFAULT 0,
                price_at_event REAL DEFAULT 0,
                FOREIGN KEY(event_id) REFERENCES events(id)
            )
            """
        )
        
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS event_reflections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                content TEXT NOT NULL,
                customer_interaction BOOLEAN DEFAULT FALSE,
                price_point_insight BOOLEAN DEFAULT FALSE,
                created_at TEXT,
                FOREIGN KEY(event_id) REFERENCES events(id)
            )
            """
        )
        
        # Goal tracking tables
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS business_goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                goal_name TEXT NOT NULL,
                goal_type TEXT NOT NULL,
                target_value REAL NOT NULL,
                target_date DATE NOT NULL,
                current_value REAL DEFAULT 0,
                measurement_unit TEXT,
                category TEXT,
                description TEXT,
                status TEXT DEFAULT 'active',
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        
        # Goal progress tracking
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS goal_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                goal_id INTEGER NOT NULL,
                progress_date DATE NOT NULL,
                value REAL NOT NULL,
                notes TEXT,
                source TEXT,
                created_at TEXT,
                FOREIGN KEY(goal_id) REFERENCES business_goals(id)
            )
            """
        )
        
        # Milestone tracking
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS goal_milestones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                goal_id INTEGER NOT NULL,
                milestone_name TEXT NOT NULL,
                target_value REAL NOT NULL,
                achieved_date DATE,
                notes TEXT,
                created_at TEXT,
                FOREIGN KEY(goal_id) REFERENCES business_goals(id)
            )
            """
        )
        
        conn.commit()

# ---------- Goal tracking functions

def create_goal(goal_data):
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        now = datetime.utcnow().isoformat()
        cur.execute(
            """
            INSERT INTO business_goals (goal_name, goal_type, target_value, target_date,
                                      measurement_unit, category, description, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                goal_data.get("goal_name"),
                goal_data.get("goal_type"),
                float(goal_data.get("target_value")),
                goal_data.get("target_date"),
                goal_data.get("measurement_unit"),
                goal_data.get("category"),
                goal_data.get("description"),
                "active",
                now,
                now,
            ),
        )
        goal_id = cur.lastrowid
        conn.commit()
        return goal_id

def update_goal_progress(goal_id, value, notes="", source="manual"):
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        now = datetime.utcnow().isoformat()
        today = date.today()
        
        # Add progress entry
        cur.execute(
            "INSERT INTO goal_progress (goal_id, progress_date, value, notes, source, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (goal_id, today, value, notes, source, now),
        )
        
        # Update current value in goals table
        cur.execute(
            "UPDATE business_goals SET current_value = ?, updated_at = ? WHERE id = ?",
            (value, now, goal_id),
        )
        conn.commit()

def get_active_goals():
    with closing(get_conn()) as conn:
        return pd.read_sql_query(
            "SELECT * FROM business_goals WHERE status = 'active' ORDER BY target_date", conn
        )

def get_goal_progress(goal_id):
    with closing(get_conn()) as conn:
        return pd.read_sql_query(
            "SELECT * FROM goal_progress WHERE goal_id = ? ORDER BY progress_date DESC", 
            conn, params=(goal_id,)
        )

def calculate_yearly_metrics(year=None):
    if year is None:
        year = date.today().year
    
    with closing(get_conn()) as conn:
        # Revenue for the year
        yearly_revenue = pd.read_sql_query(
            """
            SELECT SUM(total_revenue) as total_revenue, COUNT(*) as total_events
            FROM events 
            WHERE status = 'completed' AND strftime('%Y', event_date) = ?
            """, conn, params=(str(year),)
        )
        
        # Monthly breakdown
        monthly_breakdown = pd.read_sql_query(
            """
            SELECT strftime('%m', event_date) as month,
                   SUM(total_revenue) as revenue,
                   COUNT(*) as events
            FROM events 
            WHERE status = 'completed' AND strftime('%Y', event_date) = ?
            GROUP BY strftime('%m', event_date)
            ORDER BY month
            """, conn, params=(str(year),)
        )
        
        # Previous year comparison
        prev_year_revenue = pd.read_sql_query(
            """
            SELECT SUM(total_revenue) as total_revenue, COUNT(*) as total_events
            FROM events 
            WHERE status = 'completed' AND strftime('%Y', event_date) = ?
            """, conn, params=(str(year - 1),)
        )
        
        return yearly_revenue, monthly_breakdown, prev_year_revenue

def auto_update_goals_from_events():
    """Automatically update revenue and event count goals based on completed events"""
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        now = datetime.utcnow().isoformat()
        current_year = date.today().year
        
        # Get current year totals
        cur.execute(
            """
            SELECT SUM(total_revenue) as total_revenue, COUNT(*) as total_events
            FROM events 
            WHERE status = 'completed' AND strftime('%Y', event_date) = ?
            """, (str(current_year),)
        )
        result = cur.fetchone()
        total_revenue = result[0] or 0
        total_events = result[1] or 0
        
        # Update revenue goals
        cur.execute(
            """
            UPDATE business_goals 
            SET current_value = ?, updated_at = ?
            WHERE goal_type = 'revenue' AND status = 'active' 
            AND strftime('%Y', target_date) = ?
            """, (total_revenue, now, str(current_year))
        )
        
        # Update event count goals
        cur.execute(
            """
            UPDATE business_goals 
            SET current_value = ?, updated_at = ?
            WHERE goal_type = 'events' AND status = 'active' 
            AND strftime('%Y', target_date) = ?
            """, (total_events, now, str(current_year))
        )
        
        conn.commit()

# ---------- Event functions

def add_promotion(event_id, promotion_data):
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        now = datetime.utcnow().isoformat()
        cur.execute(
            """
            INSERT INTO event_promotions (event_id, promotion_type, platform, content, 
                                        scheduled_date, target_audience, engagement_goal, 
                                        actual_engagement, leads_generated, sales_attributed, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                promotion_data.get("promotion_type"),
                promotion_data.get("platform"),
                promotion_data.get("content"),
                promotion_data.get("scheduled_date"),
                promotion_data.get("target_audience"),
                promotion_data.get("engagement_goal"),
                promotion_data.get("actual_engagement"),
                int(promotion_data.get("leads_generated", 0) or 0),
                float(promotion_data.get("sales_attributed", 0) or 0),
                now,
            ),
        )
        conn.commit()

def get_event_promotions(event_id):
    with closing(get_conn()) as conn:
        return pd.read_sql_query(
            "SELECT * FROM event_promotions WHERE event_id = ? ORDER BY scheduled_date", 
            conn, params=(event_id,)
        )

def create_event(event_data):
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        now = datetime.utcnow().isoformat()
        cur.execute(
            """
            INSERT INTO events (name, event_date, location, event_type, theme, theme_description,
                              color_palette, target_customer, price_strategy, booth_fee, 
                              setup_time, weather, foot_traffic, total_revenue, cash_sales, 
                              card_sales, check_sales, discounts_given, rewards_given, 
                              status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_data.get("name"),
                event_data.get("event_date"),
                event_data.get("location"),
                event_data.get("event_type"),
                event_data.get("theme"),
                event_data.get("theme_description"),
                event_data.get("color_palette"),
                event_data.get("target_customer"),
                event_data.get("price_strategy"),
                float(event_data.get("booth_fee", 0) or 0),
                event_data.get("setup_time"),
                event_data.get("weather"),
                event_data.get("foot_traffic"),
                float(event_data.get("total_revenue", 0) or 0),
                float(event_data.get("cash_sales", 0) or 0),
                float(event_data.get("card_sales", 0) or 0),
                float(event_data.get("check_sales", 0) or 0),
                float(event_data.get("discounts_given", 0) or 0),
                float(event_data.get("rewards_given", 0) or 0),
                event_data.get("status", "planned"),
                now,
                now,
            ),
        )
        event_id = cur.lastrowid
        conn.commit()
        return event_id

def get_events():
    with closing(get_conn()) as conn:
        return pd.read_sql_query(
            "SELECT * FROM events ORDER BY event_date DESC", conn
        )

def get_event_by_id(event_id):
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM events WHERE id = ?", (event_id,))
        row = cur.fetchone()
        if not row:
            return None
        cols = [c[0] for c in cur.description]
        return dict(zip(cols, row))

def add_event_inventory(event_id, sku, name, brought, sold, price):
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT OR REPLACE INTO event_inventory 
            (event_id, item_sku, item_name, quantity_brought, quantity_sold, price_at_event)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (event_id, sku, name, brought, sold, price),
        )
        conn.commit()

def get_event_inventory(event_id):
    with closing(get_conn()) as conn:
        return pd.read_sql_query(
            "SELECT * FROM event_inventory WHERE event_id = ?", conn, params=(event_id,)
        )

def add_reflection(event_id, category, content, customer_interaction=False, price_point_insight=False):
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        now = datetime.utcnow().isoformat()
        cur.execute(
            "INSERT INTO event_reflections (event_id, category, content, customer_interaction, price_point_insight, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (event_id, category, content, customer_interaction, price_point_insight, now),
        )
        conn.commit()

def add_environment_data(event_id, environment_data):
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        now = datetime.utcnow().isoformat()
        cur.execute(
            """
            INSERT INTO event_environment (event_id, neighboring_vendor_left, neighboring_vendor_right,
                                         booth_location, foot_traffic_pattern, customer_demographics,
                                         competition_notes, pricing_observations, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                environment_data.get("neighboring_vendor_left"),
                environment_data.get("neighboring_vendor_right"),
                environment_data.get("booth_location"),
                environment_data.get("foot_traffic_pattern"),
                environment_data.get("customer_demographics"),
                environment_data.get("competition_notes"),
                environment_data.get("pricing_observations"),
                now,
            ),
        )
        conn.commit()

def get_environment_data(event_id):
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM event_environment WHERE event_id = ?", (event_id,))
        row = cur.fetchone()
        if not row:
            return None
        cols = [c[0] for c in cur.description]
        return dict(zip(cols, row))

def get_reflections(event_id):
    with closing(get_conn()) as conn:
        return pd.read_sql_query(
            "SELECT * FROM event_reflections WHERE event_id = ? ORDER BY created_at DESC", 
            conn, params=(event_id,)
        )

# ---------- Existing pottery functions (complete implementations)

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

# ---------- Analytics functions

def calculate_event_metrics():
    with closing(get_conn()) as conn:
        # Revenue by event type
        revenue_by_type = pd.read_sql_query(
            """
            SELECT event_type, AVG(total_revenue) as avg_revenue, 
                   COUNT(*) as event_count, SUM(total_revenue) as total_revenue
            FROM events WHERE status = 'completed'
            GROUP BY event_type
            """, conn
        )
        
        # Monthly revenue trends
        monthly_trends = pd.read_sql_query(
            """
            SELECT strftime('%Y-%m', event_date) as month, 
                   SUM(total_revenue) as revenue,
                   COUNT(*) as events
            FROM events WHERE status = 'completed'
            GROUP BY strftime('%Y-%m', event_date)
            ORDER BY month
            """, conn
        )
        
        # Top selling items across all events
        top_items = pd.read_sql_query(
            """
            SELECT item_name, SUM(quantity_sold) as total_sold,
                   AVG(price_at_event) as avg_price,
                   SUM(quantity_sold * price_at_event) as total_revenue,
                   AVG(quantity_sold * 1.0 / NULLIF(quantity_brought, 0)) as avg_sell_through_rate
            FROM event_inventory
            WHERE quantity_sold > 0
            GROUP BY item_name
            ORDER BY total_sold DESC
            LIMIT 10
            """, conn
        )
        
        # Theme performance analysis
        theme_performance = pd.read_sql_query(
            """
            SELECT theme, AVG(total_revenue) as avg_revenue,
                   COUNT(*) as event_count,
                   AVG(total_revenue - booth_fee) as avg_profit
            FROM events 
            WHERE status = 'completed' AND theme IS NOT NULL AND theme != ''
            GROUP BY theme
            ORDER BY avg_revenue DESC
            """, conn
        )
        
        # Promotion effectiveness
        promotion_effectiveness = pd.read_sql_query(
            """
            SELECT p.promotion_type, 
                   COUNT(*) as total_promotions,
                   AVG(p.sales_attributed) as avg_attributed_sales,
                   SUM(p.sales_attributed) as total_attributed_sales,
                   AVG(p.leads_generated) as avg_leads
            FROM event_promotions p
            WHERE p.sales_attributed > 0 OR p.leads_generated > 0
            GROUP BY p.promotion_type
            ORDER BY avg_attributed_sales DESC
            """, conn
        )
        
        # Price point analysis - This is the KEY missing piece
        price_analysis = pd.read_sql_query(
            """
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
            GROUP BY 
                CASE 
                    WHEN price_at_event < 20 THEN 'Under $20'
                    WHEN price_at_event < 30 THEN '$20-30'
                    WHEN price_at_event < 40 THEN '$30-40'
                    WHEN price_at_event < 50 THEN '$40-50'
                    WHEN price_at_event < 75 THEN '$50-75'
                    ELSE '$75+'
                END
            ORDER BY avg_sell_through_rate DESC
            """, conn
        )
        
        # Seasonal analysis - What sells when?
        seasonal_analysis = pd.read_sql_query(
            """
            SELECT 
                CASE 
                    WHEN CAST(strftime('%m', e.event_date) AS INTEGER) IN (12, 1, 2) THEN 'Winter'
                    WHEN CAST(strftime('%m', e.event_date) AS INTEGER) IN (3, 4, 5) THEN 'Spring'
                    WHEN CAST(strftime('%m', e.event_date) AS INTEGER) IN (6, 7, 8) THEN 'Summer'
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
            """, conn
        )
        
        # What to make more/less of - Critical business intelligence
        make_more_less = pd.read_sql_query(
            """
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
            HAVING COUNT(DISTINCT ei.event_id) >= 2  -- Only items brought to multiple events
            ORDER BY avg_sell_through_rate DESC
            """, conn
        )
        
        return revenue_by_type, monthly_trends, top_items, theme_performance, promotion_effectiveness, price_analysis, seasonal_analysis, make_more_less

def get_smart_inventory_recommendations(event_type=None, season=None):
    """Generate smart recommendations for upcoming events based on historical data"""
    with closing(get_conn()) as conn:
        # Build dynamic query based on filters
        where_conditions = ["e.status = 'completed'", "ei.quantity_brought > 0"]
        params = []
        
        if event_type:
            where_conditions.append("e.event_type = ?")
            params.append(event_type)
            
        if season:
            season_months = {
                'Winter': '(12, 1, 2)',
                'Spring': '(3, 4, 5)', 
                'Summer': '(6, 7, 8)',
                'Fall': '(9, 10, 11)'
            }
            where_conditions.append(f"CAST(strftime('%m', e.event_date) AS INTEGER) IN {season_months.get(season, '(1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12)')}")
        
        where_clause = " AND ".join(where_conditions)
        
        recommendations = pd.read_sql_query(
            f"""
            SELECT 
                ei.item_name,
                AVG(ei.quantity_brought) as avg_brought,
                AVG(ei.quantity_sold) as avg_sold,
                AVG(ei.quantity_sold * 1.0 / NULLIF(ei.quantity_brought, 0)) as avg_sell_through_rate,
                AVG(ei.price_at_event) as optimal_price,
                COUNT(DISTINCT ei.event_id) as events_count
            FROM event_inventory ei
            JOIN events e ON ei.event_id = e.id
            WHERE {where_clause}
            GROUP BY ei.item_name
            HAVING COUNT(DISTINCT ei.event_id) >= 1
            ORDER BY avg_sell_through_rate DESC
            """, conn, params=params
        )
        
        return recommendations

# ---------- UI Components

def event_form(existing=None):
    st.subheader("Event Planning")
    
    # Basic event info
    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input("Event Name", value=(existing or {}).get("name", ""))
        event_date = st.date_input("Date", value=date.today())
        location = st.text_input("Location", value=(existing or {}).get("location", ""))
        event_type = st.selectbox(
            "Event Type", 
            ["Art Fair", "Farmers Market", "Studio Sale", "Gallery Show", "Holiday Market", "Other"],
            index=0
        )
        booth_fee = st.number_input("Booth Fee", min_value=0.0, step=5.0)
    
    with col2:
        setup_time = st.text_input("Setup Time", value=(existing or {}).get("setup_time", ""))
        
    # Theme & Strategy Planning
    st.subheader("🎨 Theme & Strategy")
    
    col3, col4 = st.columns(2)
    with col3:
        theme = st.text_input("Theme/Collection Name", 
                             value=(existing or {}).get("theme", ""),
                             help="e.g., 'Blue Christmas 2021', 'Spring Pastels', 'Harvest Collection'")
        
        theme_description = st.text_area("Theme Description", 
                                       value=(existing or {}).get("theme_description", ""),
                                       help="What's the story behind this collection? What inspired it?")
        
        color_palette = st.text_input("Color Palette", 
                                    value=(existing or {}).get("color_palette", ""),
                                    help="e.g., 'Deep blues, silver accents', 'Warm earth tones'")
    
    with col4:
        target_customer = st.selectbox(
            "Target Customer",
            ["Holiday gift buyers", "Home decorators", "Collectors", "Young professionals", 
             "Families", "Art enthusiasts", "Kitchen/dining focused", "Garden lovers", "Other"],
            help="Who is this collection designed for?"
        )
        
        price_strategy = st.selectbox(
            "Pricing Strategy",
            ["Premium pricing (high-end pieces)", "Volume pricing (accessible range)", 
             "Mixed range (something for everyone)", "Gift-focused ($15-50)", 
             "Statement pieces ($75+)", "Testing new price points"]
        )
    
    # Pre-sale promotion planning
    st.subheader("📱 Pre-Sale Promotion Strategy")
    
    promotion_plan = st.text_area(
        "Promotion Plan Overview",
        help="What's your marketing approach for this event? Social media teasers, email campaigns, etc."
    )
    
    col5, col6 = st.columns(2)
    with col5:
        social_media_goal = st.text_input("Social Media Goal", 
                                        help="e.g., 'Gain 50 Instagram followers', 'Get 100 likes on preview post'")
        email_goal = st.text_input("Email Marketing Goal",
                                 help="e.g., 'Send to 150 subscribers', 'Get 10% open rate'")
    
    with col6:
        pre_sale_target = st.text_input("Pre-Sale Target",
                                      help="e.g., 'Sell 3 pieces before event', '$200 in pre-orders'")
        
        special_offers = st.text_input("Special Offers/Promotions",
                                     help="e.g., 'Early bird 10% off', 'Buy 2 mugs get free shipping'")

    # Sales tracking (for completed events)
    if st.checkbox("Mark as completed and add sales data"):
        st.subheader("📊 Event Results")
        col7, col8 = st.columns(2)
        with col7:
            total_revenue = st.number_input("Total Revenue", min_value=0.0, step=0.01)
            cash_sales = st.number_input("Cash Sales", min_value=0.0, step=0.01)
            card_sales = st.number_input("Card Sales", min_value=0.0, step=0.01)
        with col8:
            check_sales = st.number_input("Check Sales", min_value=0.0, step=0.01)
            discounts_given = st.number_input("Discounts Given", min_value=0.0, step=0.01)
            rewards_given = st.number_input("Rewards Given", min_value=0.0, step=0.01)
            
        # Event conditions
        weather = st.text_input("Weather")
        foot_traffic = st.selectbox("Foot Traffic", ["Light", "Moderate", "Heavy", "Excellent"])
        status = "completed"
    else:
        total_revenue = cash_sales = card_sales = check_sales = 0
        discounts_given = rewards_given = 0
        weather = foot_traffic = ""
        status = "planned"
    
    if st.button("Save Event", type="primary"):
        if not name:
            st.error("Event name is required")
            return None
            
        event_data = {
            "name": name,
            "event_date": event_date,
            "location": location,
            "event_type": event_type,
            "theme": theme,
            "theme_description": theme_description,
            "color_palette": color_palette,
            "target_customer": target_customer,
            "price_strategy": price_strategy,
            "booth_fee": booth_fee,
            "setup_time": setup_time,
            "weather": weather,
            "foot_traffic": foot_traffic,
            "total_revenue": total_revenue,
            "cash_sales": cash_sales,
            "card_sales": card_sales,
            "check_sales": check_sales,
            "discounts_given": discounts_given,
            "rewards_given": rewards_given,
            "status": status,
        }
        
        event_id = create_event(event_data)
        st.success(f"Event saved! ID: {event_id}")
        return event_id
    return None

def promotion_manager(event_id):
    st.subheader("📱 Promotion Planning & Tracking")
    
    # Add new promotion
    with st.expander("➕ Add New Promotion", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            promotion_type = st.selectbox(
                "Promotion Type",
                ["Social Media Post", "Instagram Story", "Email Campaign", "Facebook Event", 
                 "Website Update", "Blog Post", "Newsletter Feature", "Influencer Outreach", "Other"]
            )
            platform = st.text_input("Platform/Channel", help="e.g., Instagram, Email list, Facebook")
            scheduled_date = st.date_input("Scheduled Date")
        
        with col2:
            target_audience = st.text_input("Target Audience", 
                                          help="e.g., 'Local followers', 'Past customers', 'Holiday shoppers'")
            engagement_goal = st.text_input("Engagement Goal", 
                                          help="e.g., '50 likes', '10 comments', '5% email open rate'")
        
        content = st.text_area("Content/Message", 
                              help="What are you posting/sending? Keep it brief or paste the actual content")
        
        # Results tracking (for completed promotions)
        st.write("**Results (fill in after promotion goes live):**")
        col3, col4 = st.columns(2)
        with col3:
            actual_engagement = st.text_input("Actual Engagement", 
                                            help="e.g., '75 likes, 8 comments', '12% open rate'")
            leads_generated = st.number_input("Leads Generated", min_value=0, 
                                            help="New followers, email signups, inquiries")
        with col4:
            sales_attributed = st.number_input("Sales Attributed", min_value=0.0, step=0.01,
                                             help="Revenue you can trace back to this promotion")
        
        if st.button("Add Promotion"):
            promotion_data = {
                "promotion_type": promotion_type,
                "platform": platform,
                "content": content,
                "scheduled_date": scheduled_date,
                "target_audience": target_audience,
                "engagement_goal": engagement_goal,
                "actual_engagement": actual_engagement,
                "leads_generated": leads_generated,
                "sales_attributed": sales_attributed,
            }
            add_promotion(event_id, promotion_data)
            st.success("Promotion added!")
    
    # Show existing promotions
    promotions_df = get_event_promotions(event_id)
    if not promotions_df.empty:
        st.subheader("Promotion Timeline")
        
        for _, promo in promotions_df.iterrows():
            with st.expander(f"{promo['promotion_type']} - {promo['platform']} ({promo['scheduled_date']})"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Target Audience:** {promo['target_audience']}")
                    st.write(f"**Goal:** {promo['engagement_goal']}")
                    if promo['content']:
                        st.write(f"**Content:** {promo['content']}")
                
                with col2:
                    if promo['actual_engagement']:
                        st.write(f"**Actual Engagement:** {promo['actual_engagement']}")
                    if promo['leads_generated']:
                        st.write(f"**Leads Generated:** {promo['leads_generated']}")
                    if promo['sales_attributed']:
                        st.write(f"**Sales Attributed:** ${promo['sales_attributed']:.2f}")
        
        # Quick promotion stats
        total_attributed_sales = promotions_df['sales_attributed'].sum()
        total_leads = promotions_df['leads_generated'].sum()
        
        if total_attributed_sales > 0 or total_leads > 0:
            st.subheader("Promotion Performance Summary")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Attributed Sales", f"${total_attributed_sales:.2f}")
            with col2:
                st.metric("Total Leads Generated", int(total_leads))

def event_inventory_manager(event_id):
    st.subheader("Event Inventory")
    
    # Quick add from existing items
    items_df = fetch_items_df()
    if not items_df.empty:
        st.write("Add items from inventory:")
        selected_items = st.multiselect(
            "Select items", 
            options=items_df['sku'].tolist(),
            format_func=lambda x: f"{x} - {items_df[items_df['sku']==x]['name'].iloc[0]}"
        )
        
        if selected_items:
            for sku in selected_items:
                item = items_df[items_df['sku'] == sku].iloc[0]
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.write(f"**{item['name']}**")
                with col2:
                    brought = st.number_input(f"Brought", min_value=0, key=f"brought_{sku}")
                with col3:
                    sold = st.number_input(f"Sold", min_value=0, key=f"sold_{sku}")
                with col4:
                    price = st.number_input(f"Price", min_value=0.0, value=float(item['price']), key=f"price_{sku}")
                
                if st.button(f"Add {sku}", key=f"add_{sku}"):
                    add_event_inventory(event_id, sku, item['name'], brought, sold, price)
                    st.success(f"Added {item['name']} to event inventory")
    
    # Show current event inventory
    inventory_df = get_event_inventory(event_id)
    if not inventory_df.empty:
        st.subheader("Current Event Inventory")
        
        # Calculate sell-through rates
        inventory_df['sell_through_rate'] = (inventory_df['quantity_sold'] / inventory_df['quantity_brought'].replace(0, 1)) * 100
        inventory_df['revenue'] = inventory_df['quantity_sold'] * inventory_df['price_at_event']
        
        st.dataframe(inventory_df, use_container_width=True)
        
        # Quick stats
        total_brought = inventory_df['quantity_brought'].sum()
        total_sold = inventory_df['quantity_sold'].sum()
        total_revenue = inventory_df['revenue'].sum()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Pieces Brought", int(total_brought))
        with col2:
            st.metric("Total Pieces Sold", int(total_sold))
        with col3:
            st.metric("Total Revenue", f"${total_revenue:.2f}")

def event_reflections_manager(event_id):
    st.subheader("📝 Event Reflections & Learning")
    
    # Environment & Neighbors tracking
    with st.expander("🏪 Event Environment & Neighbors", expanded=False):
        environment_data = get_environment_data(event_id)
        
        col1, col2 = st.columns(2)
        with col1:
            neighboring_vendor_left = st.text_input("Neighboring Vendor (Left)", 
                                                   value=(environment_data or {}).get("neighboring_vendor_left", ""))
            neighboring_vendor_right = st.text_input("Neighboring Vendor (Right)", 
                                                    value=(environment_data or {}).get("neighboring_vendor_right", ""))
            booth_location = st.text_input("Booth Location/Number", 
                                         value=(environment_data or {}).get("booth_location", ""))
        
        with col2:
            foot_traffic_pattern = st.text_area("Foot Traffic Pattern", 
                                              value=(environment_data or {}).get("foot_traffic_pattern", ""),
                                              help="When was it busiest? Slow periods?")
            customer_demographics = st.text_area("Customer Demographics", 
                                                value=(environment_data or {}).get("customer_demographics", ""),
                                                help="Age groups, families vs. individuals, etc.")
        
        competition_notes = st.text_area("Competition/Similar Vendors", 
                                       value=(environment_data or {}).get("competition_notes", ""),
                                       help="Other pottery vendors, similar products, pricing observations")
        
        pricing_observations = st.text_area("Pricing Observations", 
                                          value=(environment_data or {}).get("pricing_observations", ""),
                                          help="What were others charging? Customer price reactions?")
        
        if st.button("Save Environment Data"):
            env_data = {
                "neighboring_vendor_left": neighboring_vendor_left,
                "neighboring_vendor_right": neighboring_vendor_right,
                "booth_location": booth_location,
                "foot_traffic_pattern": foot_traffic_pattern,
                "customer_demographics": customer_demographics,
                "competition_notes": competition_notes,
                "pricing_observations": pricing_observations,
            }
            add_environment_data(event_id, env_data)
            st.success("Environment data saved!")
    
    # Enhanced reflection categories
    st.subheader("Add New Reflection")
    
    col1, col2 = st.columns(2)
    with col1:
        reflection_type = st.selectbox(
            "Reflection Category", 
            ["Customer Interactions", "What Worked", "What Didn't Work", "Next Time", 
             "Pricing Insights", "Marketing Notes", "Setup & Logistics", "Competition Analysis",
             "Product Feedback", "Sales Conversations", "Display Ideas"]
        )
        
        # Special flags for important insights
        customer_interaction = st.checkbox("This is a customer interaction note", 
                                         help="Check if this note contains customer feedback or conversation details")
        price_point_insight = st.checkbox("This contains pricing insights", 
                                        help="Check if this note has insights about pricing or customer price reactions")
    
    with col2:
        reflection_content = st.text_area("Reflection Notes", height=150,
                                        help="Be specific! Include quotes, numbers, specific observations")
    
    if st.button("Add Reflection"):
        if reflection_content:
            add_reflection(event_id, reflection_type, reflection_content, customer_interaction, price_point_insight)
            st.success("Reflection added!")
    
    # Show existing reflections with better organization
    reflections_df = get_reflections(event_id)
    if not reflections_df.empty:
        st.subheader("Previous Reflections")
        
        # Quick filters
        col1, col2, col3 = st.columns(3)
        with col1:
            show_customer_interactions = st.checkbox("Show Customer Interactions Only")
        with col2:
            show_pricing_insights = st.checkbox("Show Pricing Insights Only")
        with col3:
            category_filter = st.selectbox("Filter by Category", 
                                         ["All"] + reflections_df['category'].unique().tolist())
        
        # Apply filters
        filtered_reflections = reflections_df.copy()
        if show_customer_interactions:
            filtered_reflections = filtered_reflections[filtered_reflections['customer_interaction'] == True]
        if show_pricing_insights:
            filtered_reflections = filtered_reflections[filtered_reflections['price_point_insight'] == True]
        if category_filter != "All":
            filtered_reflections = filtered_reflections[filtered_reflections['category'] == category_filter]
        
        # Display reflections
        for _, reflection in filtered_reflections.iterrows():
            # Add icons for special types
            title = f"{reflection['category']} - {reflection['created_at'][:10]}"
            if reflection['customer_interaction']:
                title = f"👥 {title}"
            if reflection['price_point_insight']:
                title = f"💰 {title}"
                
            with st.expander(title):
                st.write(reflection['content'])
        
        if filtered_reflections.empty and not reflections_df.empty:
            st.info("No reflections match your current filters.")

def goals_manager():
    st.header("🎯 Business Goals & Growth Tracking")
    
    # Auto-update goals from events
    auto_update_goals_from_events()
    
    # Current goals overview
    active_goals = get_active_goals()
    
    if not active_goals.empty:
        st.subheader("📊 Goal Progress Overview")
        
        for _, goal in active_goals.iterrows():
            progress_percentage = (goal['current_value'] / goal['target_value']) * 100 if goal['target_value'] > 0 else 0
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.write(f"**{goal['goal_name']}**")
                st.caption(f"{goal['category']}")
            with col2:
                st.metric(
                    f"Progress", 
                    f"{goal['current_value']:.0f} / {goal['target_value']:.0f} {goal['measurement_unit']}"
                )
            with col3:
                st.progress(min(progress_percentage / 100, 1.0))
                st.write(f"{progress_percentage:.1f}% complete")
            with col4:
                days_remaining = (datetime.strptime(goal['target_date'], '%Y-%m-%d').date() - date.today()).days
                if days_remaining > 0:
                    st.write(f"⏰ {days_remaining} days left")
                elif days_remaining == 0:
                    st.write("🎯 Due today!")
                else:
                    st.write(f"⚠️ {abs(days_remaining)} days overdue")
        
        st.divider()
    
    # Add new goal
    with st.expander("➕ Create New Goal", expanded=len(active_goals) == 0):
        col1, col2 = st.columns(2)
        
        with col1:
            goal_name = st.text_input("Goal Name", help="e.g., 'Annual Revenue Target', 'Number of Shows'")
            goal_type = st.selectbox("Goal Type", 
                                   ["revenue", "events", "social_media", "custom"],
                                   format_func=lambda x: {
                                       "revenue": "Revenue ($)",
                                       "events": "Number of Events",
                                       "social_media": "Social Media Growth",
                                       "custom": "Custom Metric"
                                   }[x])
            
            target_value = st.number_input("Target Value", min_value=0.0, step=1.0)
            
        with col2:
            target_date = st.date_input("Target Date", value=date(date.today().year, 12, 31))
            
            category = st.selectbox("Category", 
                                  ["Annual Goals", "Quarterly Goals", "Monthly Goals", "Growth Targets", "Other"])
            
            measurement_unit = st.text_input("Unit", 
                                           value={
                                               "revenue": "$",
                                               "events": "events",
                                               "social_media": "followers",
                                               "custom": "units"
                                           }.get(goal_type, "units"))
        
        description = st.text_area("Description", help="What does success look like? Why is this goal important?")
        
        if st.button("Create Goal", type="primary"):
            if goal_name and target_value > 0:
                goal_data = {
                    "goal_name": goal_name,
                    "goal_type": goal_type,
                    "target_value": target_value,
                    "target_date": target_date,
                    "measurement_unit": measurement_unit,
                    "category": category,
                    "description": description,
                }
                goal_id = create_goal(goal_data)
                st.success(f"Goal created! ID: {goal_id}")
                st.rerun()
            else:
                st.error("Please fill in goal name and target value")
    
    # Manual progress update
    if not active_goals.empty:
        st.subheader("📈 Update Goal Progress")
        
        goal_options = [f"{row['goal_name']} (Current: {row['current_value']:.0f})" for _, row in active_goals.iterrows()]
        selected_goal_index = st.selectbox("Select Goal to Update", range(len(goal_options)), 
                                         format_func=lambda x: goal_options[x])
        
        selected_goal = active_goals.iloc[selected_goal_index]
        
        col1, col2 = st.columns(2)
        with col1:
            new_value = st.number_input("New Value", 
                                      min_value=0.0, 
                                      value=float(selected_goal['current_value']),
                                      step=1.0)
        with col2:
            progress_notes = st.text_input("Notes (optional)", 
                                         help="What contributed to this progress?")
        
        if st.button("Update Progress"):
            update_goal_progress(selected_goal['id'], new_value, progress_notes)
            st.success("Progress updated!")
            st.rerun()

def yearly_dashboard():
    st.header("📈 Annual Business Dashboard")
    
    # Year selector
    current_year = date.today().year
    selected_year = st.selectbox("Select Year", [current_year, current_year - 1, current_year - 2], index=0)
    
    yearly_revenue, monthly_breakdown, prev_year_revenue = calculate_yearly_metrics(selected_year)
    
    # High-level metrics
    if not yearly_revenue.empty:
        total_revenue = yearly_revenue.iloc[0]['total_revenue'] or 0
        total_events = yearly_revenue.iloc[0]['total_events'] or 0
        avg_per_event = total_revenue / max(total_events, 1)
        
        # Previous year comparison
        prev_revenue = 0
        prev_events = 0
        if not prev_year_revenue.empty:
            prev_revenue = prev_year_revenue.iloc[0]['total_revenue'] or 0
            prev_events = prev_year_revenue.iloc[0]['total_events'] or 0
        
        revenue_growth = ((total_revenue - prev_revenue) / max(prev_revenue, 1)) * 100
        events_growth = ((total_events - prev_events) / max(prev_events, 1)) * 100
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Revenue", f"${total_revenue:.2f}", 
                     delta=f"{revenue_growth:+.1f}%" if prev_revenue > 0 else None)
        with col2:
            st.metric("Total Events", int(total_events),
                     delta=f"{events_growth:+.1f}%" if prev_events > 0 else None)
        with col3:
            st.metric("Avg per Event", f"${avg_per_event:.2f}")
        with col4:
            # Goal progress (if exists)
            active_goals = get_active_goals()
            revenue_goals = active_goals[
                (active_goals['goal_type'] == 'revenue') & 
                (active_goals['target_date'].str.startswith(str(selected_year)))
            ]
            if not revenue_goals.empty:
                goal = revenue_goals.iloc[0]
                goal_progress = (total_revenue / goal['target_value']) * 100
                st.metric("Goal Progress", f"{goal_progress:.1f}%",
                         delta=f"${total_revenue - goal['target_value']:.0f} to go" if goal_progress < 100 else "Goal achieved!")
    
    # Monthly breakdown
    if not monthly_breakdown.empty:
        st.subheader(f"📅 {selected_year} Monthly Breakdown")
        
        # Add month names
        month_names = {
            '01': 'Jan', '02': 'Feb', '03': 'Mar', '04': 'Apr',
            '05': 'May', '06': 'Jun', '07': 'Jul', '08': 'Aug',
            '09': 'Sep', '10': 'Oct', '11': 'Nov', '12': 'Dec'
        }
        monthly_breakdown['month_name'] = monthly_breakdown['month'].map(month_names)
        
        col1, col2 = st.columns(2)
        with col1:
            chart_data = monthly_breakdown.set_index('month_name')['revenue']
            st.subheader(f"{selected_year} Revenue by Month")
            st.bar_chart(chart_data)
        
        with col2:
            chart_data = monthly_breakdown.set_index('month_name')['revenue']
            st.subheader(f"{selected_year} Revenue Trend")
            st.line_chart(chart_data)
        
        st.dataframe(monthly_breakdown[['month_name', 'revenue', 'events']], use_container_width=True)
    
    # Year-over-year comparison
    if prev_revenue > 0:
        st.subheader("📊 Year-over-Year Comparison")
        
        comparison_data = pd.DataFrame({
            'Year': [selected_year - 1, selected_year],
            'Revenue': [prev_revenue, total_revenue],
            'Events': [prev_events, total_events]
        })
        
        col1, col2 = st.columns(2)
        with col1:
            chart_data = comparison_data.set_index('Year')['Revenue']
            st.subheader("Revenue Comparison")
            st.bar_chart(chart_data)
        
        with col2:
            chart_data = comparison_data.set_index('Year')['Events']
            st.subheader("Events Comparison")
            st.bar_chart(chart_data)
        
        # Growth insights
        if revenue_growth > 0:
            st.success(f"🎉 **Revenue Growth:** Up {revenue_growth:.1f}% from last year (${total_revenue - prev_revenue:,.2f} increase)")
        elif revenue_growth < 0:
            st.warning(f"📉 **Revenue Decline:** Down {abs(revenue_growth):.1f}% from last year")
        else:
            st.info("📊 **Revenue Stable:** Same as last year")
    
    # Goals progress for selected year
    year_goals = active_goals[active_goals['target_date'].str.startswith(str(selected_year))] if not active_goals.empty else pd.DataFrame()
    
    if not year_goals.empty:
        st.subheader(f"🎯 {selected_year} Goals Progress")
        
        for _, goal in year_goals.iterrows():
            progress_percentage = (goal['current_value'] / goal['target_value']) * 100
            
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                st.write(f"**{goal['goal_name']}**")
                st.progress(min(progress_percentage / 100, 1.0))
            with col2:
                st.metric("Progress", f"{goal['current_value']:.0f} / {goal['target_value']:.0f}")
            with col3:
                if progress_percentage >= 100:
                    st.success("🎉 Achieved!")
                elif progress_percentage >= 75:
                    st.info(f"{progress_percentage:.1f}% - Almost there!")
                else:
                    st.write(f"{progress_percentage:.1f}% complete")
    st.header("🚀 Strategic Business Intelligence")
    
    revenue_by_type, monthly_trends, top_items, theme_performance, promotion_effectiveness, price_analysis, seasonal_analysis, make_more_less = calculate_event_metrics()
    
    # High-level metrics
    with closing(get_conn()) as conn:
        total_events = pd.read_sql_query("SELECT COUNT(*) as count FROM events WHERE status = 'completed'", conn).iloc[0]['count']
        total_revenue = pd.read_sql_query("SELECT SUM(total_revenue) as total FROM events WHERE status = 'completed'", conn).iloc[0]['total'] or 0
        avg_revenue_per_event = total_revenue / max(total_events, 1)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Events", total_events)
    with col2:
        st.metric("Total Revenue", f"${total_revenue:.2f}")
    with col3:
        st.metric("Avg per Event", f"${avg_revenue_per_event:.2f}")
    
    # 🎯 STRATEGIC RECOMMENDATIONS - The most important section!
    st.subheader("🎯 Strategic Recommendations")
    
    if not make_more_less.empty:
        # Make More recommendations
        make_more = make_more_less[make_more_less['recommendation'] == 'MAKE MORE']
        make_less = make_more_less[make_more_less['recommendation'] == 'MAKE LESS']
        
        col1, col2 = st.columns(2)
        with col1:
            if not make_more.empty:
                st.success("**🔥 MAKE MORE OF THESE:**")
                for _, item in make_more.iterrows():
                    st.write(f"• **{item['item_name']}** - {item['avg_sell_through_rate']:.1%} sell-through rate")
            else:
                st.info("No high-demand items identified yet. Need more show data.")
        
        with col2:
            if not make_less.empty:
                st.warning("**⚠️ CONSIDER MAKING LESS:**")
                for _, item in make_less.iterrows():
                    st.write(f"• **{item['item_name']}** - {item['avg_sell_through_rate']:.1%} sell-through rate")
            else:
                st.success("No underperforming items identified!")
        
        # Full make more/less analysis
        st.subheader("📊 Complete Product Performance Analysis")
        st.dataframe(make_more_less, use_container_width=True)
    
    # 💰 PRICE POINT ANALYSIS - Critical for pricing strategy
    if not price_analysis.empty:
        st.subheader("💰 Price Point Performance")
        
        col1, col2 = st.columns(2)
        with col1:
            chart_data = price_analysis.set_index('price_range')['avg_sell_through_rate']
            st.subheader("Sell-Through Rate by Price Range")
            st.bar_chart(chart_data)
            st.caption("Higher bars = better sell-through rates")
        
        with col2:
            chart_data = price_analysis.set_index('price_range')['total_revenue']
            st.subheader("Total Revenue by Price Range")
            st.bar_chart(chart_data)
        
        # Price insights
        best_price_range = price_analysis.loc[price_analysis['avg_sell_through_rate'].idxmax()]
        st.info(f"🎯 **Sweet Spot:** The **{best_price_range['price_range']}** range has the highest sell-through rate at {best_price_range['avg_sell_through_rate']:.1%}")
        
        st.dataframe(price_analysis, use_container_width=True)
    
    # 🌱 SEASONAL ANALYSIS
    if not seasonal_analysis.empty:
        st.subheader("🌱 Seasonal Trends")
        
        # Create seasonal summary
        seasonal_summary = seasonal_analysis.groupby('season').agg({
            'total_sold': 'sum',
            'avg_sell_through_rate': 'mean',
            'item_name': 'count'
        }).round(3)
        seasonal_summary.columns = ['Total Sold', 'Avg Sell-Through', 'Product Varieties']
        
        col1, col2 = st.columns(2)
        with col1:
            chart_data = seasonal_summary.reset_index().set_index('season')['Total Sold']
            st.subheader("Sales Volume by Season")
            st.bar_chart(chart_data)
        
        with col2:
            chart_data = seasonal_summary.reset_index().set_index('season')['Avg Sell-Through']
            st.subheader("Sell-Through Rate by Season")
            st.bar_chart(chart_data)
        
        # Best sellers by season
        st.write("**Top Items by Season:**")
        for season in seasonal_analysis['season'].unique():
            season_data = seasonal_analysis[seasonal_analysis['season'] == season].head(3)
            st.write(f"**{season}:** {', '.join(season_data['item_name'].tolist())}")
    
    # 🎯 SMART INVENTORY PLANNER
    st.subheader("🎯 Smart Event Planning")
    
    col1, col2 = st.columns(2)
    with col1:
        plan_event_type = st.selectbox("Event Type", 
                                     [""] + revenue_by_type['event_type'].tolist() if not revenue_by_type.empty else [""],
                                     help="Get recommendations based on this event type")
    with col2:
        plan_season = st.selectbox("Season", 
                                 ["", "Winter", "Spring", "Summer", "Fall"],
                                 help="Get seasonal recommendations")
    
    if plan_event_type or plan_season:
        recommendations = get_smart_inventory_recommendations(
            event_type=plan_event_type if plan_event_type else None,
            season=plan_season if plan_season else None
        )
        
        if not recommendations.empty:
            st.subheader(f"📋 Recommended Inventory for {plan_event_type} {plan_season} Event")
            
            # Sort by sell-through rate and show top recommendations
            top_recommendations = recommendations.head(10)
            
            for _, item in top_recommendations.iterrows():
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.write(f"**{item['item_name']}**")
                with col2:
                    st.write(f"Bring: {item['avg_brought']:.0f}")
                with col3:
                    st.write(f"Expected to sell: {item['avg_sold']:.0f}")
                with col4:
                    st.write(f"Success rate: {item['avg_sell_through_rate']:.1%}")
            
            # Check current inventory vs recommendations
            current_inventory = fetch_items_df()
            if not current_inventory.empty:
                st.subheader("📦 Current Stock vs Recommendations")
                
                for _, rec in top_recommendations.head(5).iterrows():
                    matching_item = current_inventory[current_inventory['name'].str.contains(rec['item_name'], case=False, na=False)]
                    if not matching_item.empty:
                        current_stock = matching_item.iloc[0]['qty_on_hand']
                        recommended = rec['avg_brought']
                        
                        if current_stock < recommended:
                            st.warning(f"⚠️ **{rec['item_name']}**: You have {current_stock:.0f}, recommend bringing {recommended:.0f}")
                        else:
                            st.success(f"✅ **{rec['item_name']}**: You have {current_stock:.0f}, recommend {recommended:.0f}")
        else:
            st.info("No data available for this event type/season combination yet.")
    
    # Revenue analysis
    if not revenue_by_type.empty:
        st.subheader("💰 Revenue Analysis")
        col1, col2 = st.columns(2)
        
        with col1:
            fig = px.bar(revenue_by_type, x='event_type', y='avg_revenue', 
                        title="Average Revenue by Event Type")
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            if not monthly_trends.empty:
                fig = px.line(monthly_trends, x='month', y='revenue', 
                             title="Revenue Trends Over Time")
                st.plotly_chart(fig, use_container_width=True)
    
    # Theme performance analysis
    if not theme_performance.empty:
        st.subheader("🎨 Theme Performance Analysis")
        st.dataframe(theme_performance, use_container_width=True)
        
        chart_data = theme_performance.head(5).set_index('theme')['avg_revenue']
        st.subheader("Top 5 Performing Themes by Average Revenue")
        st.bar_chart(chart_data)
    
    # Promotion effectiveness
    if not promotion_effectiveness.empty:
        st.subheader("📱 Promotion Effectiveness")
        
        col1, col2 = st.columns(2)
        with col1:
            st.dataframe(promotion_effectiveness, use_container_width=True)
        
        with col2:
            chart_data = promotion_effectiveness.set_index('promotion_type')['avg_attributed_sales']
            st.subheader("Average Sales by Promotion Type")
            st.bar_chart(chart_data)
        
        # ROI calculation for promotions
        total_promotion_sales = promotion_effectiveness['total_attributed_sales'].sum()
        if total_promotion_sales > 0:
            st.success(f"🎯 **Promotion ROI:** Your marketing efforts have generated ${total_promotion_sales:.2f} in attributed sales!")
    
    # Product performance
    if not top_items.empty:
        st.subheader("🏆 Product Performance")
        
        col1, col2 = st.columns(2)
        with col1:
            st.dataframe(top_items, use_container_width=True)
        
        with col2:
            chart_data = top_items.head(5).set_index('item_name')['total_sold']
            st.subheader("Top 5 Best Selling Items")
            st.bar_chart(chart_data)
    
    # Strategic insights summary
    st.subheader("🧠 Strategic Insights Summary")
    
    insights = []
    
    # Event type insights
    if not revenue_by_type.empty:
        best_event_type = revenue_by_type.loc[revenue_by_type['avg_revenue'].idxmax()]
        insights.append(f"🎪 **{best_event_type['event_type']}** events generate the highest average revenue (${best_event_type['avg_revenue']:.2f})")
    
    # Price point insights
    if not price_analysis.empty:
        best_price_range = price_analysis.loc[price_analysis['avg_sell_through_rate'].idxmax()]
        insights.append(f"💰 **{best_price_range['price_range']}** is your sweet spot price range with {best_price_range['avg_sell_through_rate']:.1%} sell-through rate")
    
    # Theme insights
    if not theme_performance.empty:
        best_theme = theme_performance.iloc[0]
        insights.append(f"🎨 **'{best_theme['theme']}'** is your most successful theme with ${best_theme['avg_revenue']:.2f} average revenue")
    
    # Make more insights
    if not make_more_less.empty:
        high_performers = make_more_less[make_more_less['recommendation'] == 'MAKE MORE']
        if not high_performers.empty:
            top_performer = high_performers.iloc[0]
            insights.append(f"🔥 **{top_performer['item_name']}** is in high demand with {top_performer['avg_sell_through_rate']:.1%} sell-through rate")
    
    # Promotion insights
    if not promotion_effectiveness.empty:
        best_promotion = promotion_effectiveness.iloc[0]
        insights.append(f"📱 **{best_promotion['promotion_type']}** promotions are most effective, generating ${best_promotion['avg_attributed_sales']:.2f} average attributed sales")
    
    for insight in insights:
        st.write(insight)
        
    if not insights:
        st.info("Complete a few events with detailed tracking to start seeing strategic insights!")

# ---------- Main App

st.set_page_config(page_title="Pottery Shop & Events", page_icon="🧱", layout="wide")
init_db()

menu = st.sidebar.selectbox("Go to", [
    "Dashboard", 
    "Items", 
    "New item", 
    "Import or Export",
    "Shows & Events",
    "New Event",
    "Event Analytics",
    "Smart Planning",
    "Business Goals",
    "Yearly Dashboard"
    "📅 New Event",
    "🎯 Smart Planning", 
    "📋 Manage Events",
    "📊 Event Analytics",
    "🏠 Dashboard",
    "🏺 Items",
    "➕ New Item",
    "📈 Business Goals",
    "📆 Yearly Review",
    "💾 Import/Export"
])  

# Existing menu items (simplified for space)
if menu == "🏠 Dashboard":
    st.header("Pottery Shop & Business Intelligence")
    st.write("Complete pottery business management: inventory, shows, strategy, and growth tracking.")
    
    # Quick stats with goal integration
    events_df = get_events()
    current_year = date.today().year
    
    col1, col2, col3 = st.columns(3)
    
    if not events_df.empty:
        completed_events = events_df[events_df['status'] == 'completed']
        current_year_events = completed_events[
            pd.to_datetime(completed_events['event_date']).dt.year == current_year
        ]
        
        if not current_year_events.empty:
            with col1:
                st.metric("This Year's Shows", len(current_year_events))
            with col2:
                st.metric("This Year's Revenue", f"${current_year_events['total_revenue'].sum():.2f}")
            with col3:
                st.metric("Average per Show", f"${current_year_events['total_revenue'].mean():.2f}")
    
    # Goal progress overview
    auto_update_goals_from_events()
    active_goals = get_active_goals()
    
    if not active_goals.empty:
        st.subheader("🎯 Goal Progress Summary")
        
        current_year_goals = active_goals[active_goals['target_date'].str.startswith(str(current_year))]
        
        if not current_year_goals.empty:
            for _, goal in current_year_goals.head(3).iterrows():  # Show top 3 goals
                progress_percentage = (goal['current_value'] / goal['target_value']) * 100 if goal['target_value'] > 0 else 0
                
                col1, col2, col3 = st.columns([2, 1, 1])
                with col1:
                    st.write(f"**{goal['goal_name']}**")
                    st.progress(min(progress_percentage / 100, 1.0))
                with col2:
                    st.write(f"{goal['current_value']:.0f} / {goal['target_value']:.0f}")
                with col3:
                    if progress_percentage >= 100:
                        st.success("🎉 Done!")
                    else:
                        st.write(f"{progress_percentage:.1f}%")
        
        if len(active_goals) > 3:
            st.info(f"View all {len(active_goals)} goals in Business Goals section")
    else:
        st.info("💡 Set up your first business goal to track progress throughout the year!")
    
    # Recent items summary
    df = fetch_items_df()
    if not df.empty:
        top = df[["sku", "name", "qty_on_hand", "price", "category", "glaze", "updated_at"]].head(10)
        st.subheader("Recent Items")
        st.dataframe(top, use_container_width=True)
        
        # Download button for items
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("Download All Items CSV", data=csv, file_name="pottery_items.csv", mime="text/csv")
    else:
        st.info("No items in inventory yet. Add your first pottery piece!")

elif menu == "📅 New Event":
    st.header("📅 Create New Event")
    event_form()
    st.header("Pottery Shop & Business Intelligence")
    st.write("Complete pottery business management: inventory, shows, strategy, and growth tracking.")
    
    # Quick stats with goal integration
    events_df = get_events()
    current_year = date.today().year
    
    col1, col2, col3 = st.columns(3)
    
    if not events_df.empty:
        completed_events = events_df[events_df['status'] == 'completed']
        current_year_events = completed_events[
            pd.to_datetime(completed_events['event_date']).dt.year == current_year
        ]
        
        if not current_year_events.empty:
            with col1:
                st.metric("This Year's Shows", len(current_year_events))
            with col2:
                st.metric("This Year's Revenue", f"${current_year_events['total_revenue'].sum():.2f}")
            with col3:
                st.metric("Average per Show", f"${current_year_events['total_revenue'].mean():.2f}")
    
    # Goal progress overview
    auto_update_goals_from_events()
    active_goals = get_active_goals()
    
    if not active_goals.empty:
        st.subheader("🎯 Goal Progress Summary")
        
        current_year_goals = active_goals[active_goals['target_date'].str.startswith(str(current_year))]
        
        if not current_year_goals.empty:
            for _, goal in current_year_goals.head(3).iterrows():  # Show top 3 goals
                progress_percentage = (goal['current_value'] / goal['target_value']) * 100 if goal['target_value'] > 0 else 0
                
                col1, col2, col3 = st.columns([2, 1, 1])
                with col1:
                    st.write(f"**{goal['goal_name']}**")
                    st.progress(min(progress_percentage / 100, 1.0))
                with col2:
                    st.write(f"{goal['current_value']:.0f} / {goal['target_value']:.0f}")
                with col3:
                    if progress_percentage >= 100:
                        st.success("🎉 Done!")
                    else:
                        st.write(f"{progress_percentage:.1f}%")
        
        if len(active_goals) > 3:
            st.info(f"View all {len(active_goals)} goals in Business Goals section")
    else:
        st.info("💡 Set up your first business goal to track progress throughout the year!")
    
    # Recent items summary
    df = fetch_items_df()
    if not df.empty:
        top = df[["sku", "name", "qty_on_hand", "price", "category", "glaze", "updated_at"]].head(10)
        st.subheader("Recent Items")
        st.dataframe(top, use_container_width=True)
        
        # Download button for items
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("Download All Items CSV", data=csv, file_name="pottery_items.csv", mime="text/csv")
    else:
        st.info("No items in inventory yet. Add your first pottery piece!")

elif menu == "📋 Shows & Events":
    st.header("Shows & Events")
    
    events_df = get_events()
    if not events_df.empty:
        st.dataframe(events_df, use_container_width=True)
        
        # Event selector
        event_names = [f"{row['name']} - {row['event_date']}" for _, row in events_df.iterrows()]
        selected_event = st.selectbox("Select an event to manage", event_names)
        
        if selected_event:
            event_id = events_df.iloc[event_names.index(selected_event)]['id']
            event = get_event_by_id(event_id)
            
            st.subheader(f"Managing: {event['name']}")
            
            tab1, tab2, tab3, tab4 = st.tabs(["Event Strategy", "Promotions", "Inventory", "Reflections"])
            
            with tab1:
                # Show theme and strategy info
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Theme:** {event['theme']}")
                    if event['theme_description']:
                        st.write(f"**Description:** {event['theme_description']}")
                    if event['color_palette']:
                        st.write(f"**Colors:** {event['color_palette']}")
                
                with col2:
                    st.write(f"**Target Customer:** {event['target_customer']}")
                    st.write(f"**Price Strategy:** {event['price_strategy']}")
                    st.write(f"**Status:** {event['status']}")
                    
                if event['status'] == 'completed':
                    st.subheader("Financial Results")
                    col3, col4, col5 = st.columns(3)
                    with col3:
                        st.metric("Total Revenue", f"${event['total_revenue']:.2f}")
                    with col4:
                        st.metric("Net Revenue", f"${event['total_revenue'] - event['booth_fee']:.2f}")
                    with col5:
                        st.metric("ROI", f"{((event['total_revenue'] - event['booth_fee']) / max(event['booth_fee'], 1) * 100):.1f}%")
            
            with tab2:
                promotion_manager(event_id)
            
            with tab3:
                event_inventory_manager(event_id)
            
            with tab4:
                event_reflections_manager(event_id)
    else:
        st.info("No events yet. Create your first event!")

elif menu == "📅 New Event":
    st.header("New Event")
    event_form()

elif menu == "📊 Event Analytics":
    analytics_dashboard()

elif menu == "🎯 Smart Planning":
    st.header("🎯 Smart Event Planning Assistant")
    
    st.write("Plan your next event based on historical data and strategic insights.")
    
    # Event planning form
    col1, col2 = st.columns(2)
    with col1:
        upcoming_event_type = st.selectbox("Upcoming Event Type", 
                                         ["Art Fair", "Farmers Market", "Studio Sale", "Gallery Show", "Holiday Market", "Other"])
        upcoming_season = st.selectbox("Season", ["Winter", "Spring", "Summer", "Fall"])
        
    with col2:
        target_revenue = st.number_input("Target Revenue Goal", min_value=0.0, step=100.0, value=1000.0)
        booth_fee = st.number_input("Booth Fee", min_value=0.0, step=25.0)
    
    if st.button("Generate Smart Recommendations", type="primary"):
        st.subheader("📋 Your Personalized Event Plan")
        
        # Get recommendations
        recommendations = get_smart_inventory_recommendations(upcoming_event_type, upcoming_season)
        
        if not recommendations.empty:
            st.success("✅ **Inventory Recommendations Based on Your Historical Data:**")
            
            total_expected_revenue = 0
            for _, item in recommendations.head(8).iterrows():
                expected_revenue = item['avg_sold'] * item['optimal_price']
                total_expected_revenue += expected_revenue
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.write(f"**{item['item_name']}**")
                with col2:
                    st.write(f"Bring: {item['avg_brought']:.0f} pieces")
                with col3:
                    st.write(f"Price at: ${item['optimal_price']:.2f}")
                with col4:
                    st.write(f"Expected: ${expected_revenue:.2f}")
            
            # Revenue projection
            st.subheader("💰 Revenue Projection")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Expected Revenue", f"${total_expected_revenue:.2f}")
            with col2:
                st.metric("Target Revenue", f"${target_revenue:.2f}")
            with col3:
                difference = total_expected_revenue - target_revenue
                st.metric("Difference", f"${difference:.2f}", delta=f"{difference:.2f}")
            
            # Profit analysis
            expected_profit = total_expected_revenue - booth_fee
            st.metric("Expected Profit", f"${expected_profit:.2f}")
            
            if expected_profit > 0:
                roi = (expected_profit / max(booth_fee, 1)) * 100
                st.success(f"🎯 **Expected ROI:** {roi:.1f}%")
            
            # Strategic suggestions
            st.subheader("🧠 Strategic Suggestions")
            
            if total_expected_revenue < target_revenue:
                shortfall = target_revenue - total_expected_revenue
                st.warning(f"⚠️ You're ${shortfall:.2f} short of your revenue goal. Consider:")
                st.write("• Bringing higher-priced items")
                st.write("• Adding more of your best-selling pieces")
                st.write("• Testing a premium pricing strategy")
            else:
                st.success("🎉 Your plan exceeds your revenue goal! You're on track for a successful event.")
            
            # Current stock check
            current_inventory = fetch_items_df()
            if not current_inventory.empty:
                st.subheader("📦 Stock Status Check")
                
                for _, rec in recommendations.head(5).iterrows():
                    matching_items = current_inventory[
                        current_inventory['name'].str.contains(rec['item_name'], case=False, na=False)
                    ]
                    
                    if not matching_items.empty:
                        current_stock = matching_items.iloc[0]['qty_on_hand']
                        recommended = rec['avg_brought']
                        
                        if current_stock < recommended:
                            st.error(f"🚨 **{rec['item_name']}**: Need {recommended:.0f}, have {current_stock:.0f} - Make {recommended - current_stock:.0f} more!")
                        elif current_stock < recommended * 1.2:
                            st.warning(f"⚠️ **{rec['item_name']}**: Cutting it close - have {current_stock:.0f}, recommend {recommended:.0f}")
                        else:
                            st.success(f"✅ **{rec['item_name']}**: Well stocked - have {current_stock:.0f}, need {recommended:.0f}")
        else:
            st.info("No historical data available for this event type/season combination. Complete a few events to get personalized recommendations!")
    
    # Quick insights from past similar events
    st.subheader("📊 Insights from Similar Events")
    
    with closing(get_conn()) as conn:
        similar_events = pd.read_sql_query(
            """
            SELECT name, event_date, total_revenue, 
                   (total_revenue - booth_fee) as profit,
                   weather, foot_traffic
            FROM events 
            WHERE event_type = ? AND status = 'completed'
            ORDER BY event_date DESC
            LIMIT 5
            """, conn, params=(upcoming_event_type,)
        )
    
    if not similar_events.empty:
        st.dataframe(similar_events, use_container_width=True)
        avg_revenue = similar_events['total_revenue'].mean()
        st.info(f"💡 **Historical Average:** Similar {upcoming_event_type} events averaged ${avg_revenue:.2f} revenue")
    else:
        st.info(f"No historical data for {upcoming_event_type} events yet.")

# Add other existing menu items here (Items, New item, etc.)
elif menu == "📈 Business Goals":
    goals_manager()

elif menu == "📆 Yearly Dashboard":
    yearly_dashboard()

elif menu == "🏺 Items":
    st.header("Items")
    q = st.text_input("Search by name, sku, category, glaze, clay body")
    df = fetch_items_df(q)
    st.dataframe(df, use_container_width=True)

elif menu == "New item":
    st.header("New item")
    # Simplified for space - would include the full item_form() here

elif menu == "Import or Export":
    st.header("Import or Export")
    st.info("Import/export functionality would be here")
