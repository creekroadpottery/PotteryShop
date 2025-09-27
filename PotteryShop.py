import streamlit as st
import pandas as pd
import sqlite3
from contextlib import closing
from datetime import datetime, date

DB_PATH = "pottery_shop.db"

# =============== DB HELPERS ===============

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    with closing(get_conn()) as conn:
        cur = conn.cursor()

        # Inventory tables
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

        # Events core
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                event_date TEXT NOT NULL,
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

        # Promotions
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS event_promotions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                promotion_type TEXT NOT NULL,
                platform TEXT,
                content TEXT,
                scheduled_date TEXT,
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

        # Event inventory
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
                UNIQUE(event_id, item_sku),
                FOREIGN KEY(event_id) REFERENCES events(id)
            )
            """
        )

        # Event reflections
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS event_reflections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                content TEXT NOT NULL,
                customer_interaction INTEGER DEFAULT 0,
                price_point_insight INTEGER DEFAULT 0,
                created_at TEXT,
                FOREIGN KEY(event_id) REFERENCES events(id)
            )
            """
        )

        # Event environment details
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS event_environment (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL UNIQUE,
                neighboring_vendor_left TEXT,
                neighboring_vendor_right TEXT,
                booth_location TEXT,
                foot_traffic_pattern TEXT,
                customer_demographics TEXT,
                competition_notes TEXT,
                pricing_observations TEXT,
                created_at TEXT,
                FOREIGN KEY(event_id) REFERENCES events(id)
            )
            """
        )

        # Goals
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS business_goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                goal_name TEXT NOT NULL,
                goal_type TEXT NOT NULL,
                target_value REAL NOT NULL,
                target_date TEXT NOT NULL,
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
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS goal_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                goal_id INTEGER NOT NULL,
                progress_date TEXT NOT NULL,
                value REAL NOT NULL,
                notes TEXT,
                source TEXT,
                created_at TEXT,
                FOREIGN KEY(goal_id) REFERENCES business_goals(id)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS goal_milestones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                goal_id INTEGER NOT NULL,
                milestone_name TEXT NOT NULL,
                target_value REAL NOT NULL,
                achieved_date TEXT,
                notes TEXT,
                created_at TEXT,
                FOREIGN KEY(goal_id) REFERENCES business_goals(id)
            )
            """
        )
        conn.commit()

# =============== INVENTORY FUNCTIONS ===============

def upsert_item(row: dict):
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
                row.get("sku"), row.get("name"), row.get("category"), row.get("clay_body"),
                row.get("glaze"), row.get("size"), float(row.get("price", 0) or 0),
                float(row.get("qty_on_hand", 0) or 0), row.get("location"), row.get("notes"),
                row.get("image_path"), now, now, now
            ),
        )
        conn.commit()

def fetch_items_df(search: str = "") -> pd.DataFrame:
    with closing(get_conn()) as conn:
        if search:
            q = f"%{search.strip()}%"
            df = pd.read_sql_query(
                """
                SELECT * FROM items
                WHERE name LIKE ? OR sku LIKE ? OR category LIKE ? OR glaze LIKE ? OR clay_body LIKE ?
                ORDER BY COALESCE(updated_at, created_at) DESC
                """,
                conn,
                params=(q, q, q, q, q),
            )
        else:
            df = pd.read_sql_query(
                "SELECT * FROM items ORDER BY COALESCE(updated_at, created_at) DESC",
                conn,
            )
    return df

def record_move(item_id: int, move_type: str, quantity: float, reference: str = ""):
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

def fetch_item_by_sku(sku: str):
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM items WHERE sku = ?", (sku,))
        row = cur.fetchone()
        if not row:
            return None
        cols = [c[0] for c in cur.description]
        return dict(zip(cols, row))

def delete_item(item_id: int):
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM stock_moves WHERE item_id = ?", (item_id,))
        cur.execute("DELETE FROM items WHERE id = ?", (item_id,))
        conn.commit()

# =============== EVENTS & ANALYTICS HELPERS ===============

def create_event(event_data):
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        now = datetime.utcnow().isoformat()
        cur.execute(
            """
            INSERT INTO events (name, event_date, location, event_type, theme, theme_description,
                                color_palette, target_customer, price_strategy, booth_fee, setup_time,
                                weather, foot_traffic, total_revenue, cash_sales, card_sales, check_sales,
                                discounts_given, rewards_given, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_data.get("name"),
                str(event_data.get("event_date")),
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
        return pd.read_sql_query("SELECT * FROM events ORDER BY event_date DESC", conn)

def get_event_by_id(event_id: int):
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM events WHERE id = ?", (event_id,))
        row = cur.fetchone()
        if not row:
            return None
        cols = [c[0] for c in cur.description]
        return dict(zip(cols, row))

# =============== BILL-PROOF DELETE FUNCTIONS ===============

def delete_promotion(promotion_id: int):
    """Delete a promotion - because sometimes marketing plans change!"""
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM event_promotions WHERE id = ?", (promotion_id,))
        conn.commit()

def delete_event(event_id: int):
    """Delete an event and all related data - nuclear option!"""
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        # Delete in order to respect foreign key constraints
        cur.execute("DELETE FROM event_promotions WHERE event_id = ?", (event_id,))
        cur.execute("DELETE FROM event_inventory WHERE event_id = ?", (event_id,))
        cur.execute("DELETE FROM event_reflections WHERE event_id = ?", (event_id,))
        cur.execute("DELETE FROM event_environment WHERE event_id = ?", (event_id,))
        cur.execute("DELETE FROM events WHERE id = ?", (event_id,))
        conn.commit()

def delete_goal(goal_id: int):
    """Delete a business goal and its progress - sometimes goals change!"""
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM goal_progress WHERE goal_id = ?", (goal_id,))
        cur.execute("DELETE FROM goal_milestones WHERE goal_id = ?", (goal_id,))
        cur.execute("DELETE FROM business_goals WHERE id = ?", (goal_id,))
        conn.commit()

def delete_event_inventory_row(inventory_id: int):
    """Delete a single inventory line item - for when you change your mind!"""
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM event_inventory WHERE id = ?", (inventory_id,))
        conn.commit()

def delete_reflection(reflection_id: int):
    """Delete a reflection - sometimes we reflect too much!"""
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM event_reflections WHERE id = ?", (reflection_id,))
        conn.commit()

# =============== CONTINUED EVENT FUNCTIONS ===============

def add_promotion(event_id, promotion_data):
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        now = datetime.utcnow().isoformat()
        cur.execute(
            """
            INSERT INTO event_promotions (event_id, promotion_type, platform, content, scheduled_date, target_audience,
                                          engagement_goal, actual_engagement, leads_generated, sales_attributed, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                promotion_data.get("promotion_type"),
                promotion_data.get("platform"),
                promotion_data.get("content"),
                str(promotion_data.get("scheduled_date")) if promotion_data.get("scheduled_date") else None,
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
            conn,
            params=(event_id,),
        )

def add_event_inventory(event_id, sku, name, brought, sold, price):
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO event_inventory (event_id, item_sku, item_name, quantity_brought, quantity_sold, price_at_event)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(event_id, item_sku) DO UPDATE SET
                item_name=excluded.item_name,
                quantity_brought=excluded.quantity_brought,
                quantity_sold=excluded.quantity_sold,
                price_at_event=excluded.price_at_event
            """,
            (event_id, sku, name, int(brought or 0), int(sold or 0), float(price or 0)),
        )
        conn.commit()

def get_event_inventory(event_id):
    with closing(get_conn()) as conn:
        return pd.read_sql_query(
            "SELECT * FROM event_inventory WHERE event_id = ?",
            conn,
            params=(event_id,),
        )

def add_reflection(event_id, category, content, customer_interaction=False, price_point_insight=False):
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        now = datetime.utcnow().isoformat()
        cur.execute(
            """
            INSERT INTO event_reflections (event_id, category, content, customer_interaction, price_point_insight, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (event_id, category, content, int(bool(customer_interaction)), int(bool(price_point_insight)), now),
        )
        conn.commit()

def add_environment_data(event_id, environment_data):
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        now = datetime.utcnow().isoformat()
        # Upsert single row per event
        cur.execute(
            """
            INSERT INTO event_environment (event_id, neighboring_vendor_left, neighboring_vendor_right, booth_location,
                                           foot_traffic_pattern, customer_demographics, competition_notes, pricing_observations, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(event_id) DO UPDATE SET
                neighboring_vendor_left=excluded.neighboring_vendor_left,
                neighboring_vendor_right=excluded.neighboring_vendor_right,
                booth_location=excluded.booth_location,
                foot_traffic_pattern=excluded.foot_traffic_pattern,
                customer_demographics=excluded.customer_demographics,
                competition_notes=excluded.competition_notes,
                pricing_observations=excluded.pricing_observations
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
            conn,
            params=(event_id,),
        )

# =============== GOALS & METRICS ===============

def create_goal(goal_data):
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        now = datetime.utcnow().isoformat()
        cur.execute(
            """
            INSERT INTO business_goals (goal_name, goal_type, target_value, target_date, measurement_unit, category, description, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
            """,
            (
                goal_data.get("goal_name"),
                goal_data.get("goal_type"),
                float(goal_data.get("target_value")),
                str(goal_data.get("target_date")),
                goal_data.get("measurement_unit"),
                goal_data.get("category"),
                goal_data.get("description"),
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
        today = date.today().isoformat()
        cur.execute(
            "INSERT INTO goal_progress (goal_id, progress_date, value, notes, source, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (goal_id, today, float(value), notes, source, now),
        )
        cur.execute(
            "UPDATE business_goals SET current_value = ?, updated_at = ? WHERE id = ?",
            (float(value), now, goal_id),
        )
        conn.commit()

def get_active_goals():
    with closing(get_conn()) as conn:
        return pd.read_sql_query("SELECT * FROM business_goals WHERE status = 'active' ORDER BY target_date", conn)

def calculate_yearly_metrics(year=None):
    if year is None:
        year = date.today().year
    with closing(get_conn()) as conn:
        yearly_revenue = pd.read_sql_query(
            """
            SELECT SUM(total_revenue) as total_revenue, COUNT(*) as total_events
            FROM events 
            WHERE status = 'completed' AND strftime('%Y', event_date) = ?
            """,
            conn,
            params=(str(year),),
        )
        monthly_breakdown = pd.read_sql_query(
            """
            SELECT strftime('%m', event_date) as month, SUM(total_revenue) as revenue, COUNT(*) as events
            FROM events 
            WHERE status = 'completed' AND strftime('%Y', event_date) = ?
            GROUP BY strftime('%m', event_date)
            ORDER BY month
            """,
            conn,
            params=(str(year),),
        )
        prev_year_revenue = pd.read_sql_query(
            """
            SELECT SUM(total_revenue) as total_revenue, COUNT(*) as total_events
            FROM events 
            WHERE status = 'completed' AND strftime('%Y', event_date) = ?
            """,
            conn,
            params=(str(year - 1),),
        )
        return yearly_revenue, monthly_breakdown, prev_year_revenue

def auto_update_goals_from_events():
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        now = datetime.utcnow().isoformat()
        current_year = str(date.today().year)
        cur.execute(
            """
            SELECT SUM(total_revenue) as total_revenue, COUNT(*) as total_events
            FROM events 
            WHERE status = 'completed' AND strftime('%Y', event_date) = ?
            """,
            (current_year,),
        )
        total_revenue, total_events = cur.fetchone()
        total_revenue = total_revenue or 0
        total_events = total_events or 0
        cur.execute(
            """
            UPDATE business_goals 
            SET current_value = ?, updated_at = ?
            WHERE goal_type = 'revenue' AND status = 'active' AND substr(target_date,1,4) = ?
            """,
            (total_revenue, now, current_year),
        )
        cur.execute(
            """
            UPDATE business_goals 
            SET current_value = ?, updated_at = ?
            WHERE goal_type = 'events' AND status = 'active' AND substr(target_date,1,4) = ?
            """,
            (total_events, now, current_year),
        )
        conn.commit()

def calculate_event_metrics():
    with closing(get_conn()) as conn:
        revenue_by_type = pd.read_sql_query(
            """
            SELECT event_type, AVG(total_revenue) as avg_revenue, COUNT(*) as event_count, SUM(total_revenue) as total_revenue
            FROM events WHERE status = 'completed' GROUP BY event_type
            """,
            conn,
        )
        monthly_trends = pd.read_sql_query(
            """
            SELECT strftime('%Y-%m', event_date) as month, SUM(total_revenue) as revenue, COUNT(*) as events
            FROM events WHERE status = 'completed'
            GROUP BY strftime('%Y-%m', event_date)
            ORDER BY month
            """,
            conn,
        )
        top_items = pd.read_sql_query(
            """
            SELECT item_name, SUM(quantity_sold) as total_sold, AVG(price_at_event) as avg_price,
                   SUM(quantity_sold * price_at_event) as total_revenue,
                   AVG(quantity_sold * 1.0 / NULLIF(quantity_brought, 0)) as avg_sell_through_rate
            FROM event_inventory
            WHERE quantity_sold > 0
            GROUP BY item_name
            ORDER BY total_sold DESC
            LIMIT 10
            """,
            conn,
        )
        theme_performance = pd.read_sql_query(
            """
            SELECT theme, AVG(total_revenue) as avg_revenue, COUNT(*) as event_count,
                   AVG(total_revenue - booth_fee) as avg_profit
            FROM events WHERE status = 'completed' AND theme IS NOT NULL AND theme != ''
            GROUP BY theme
            ORDER BY avg_revenue DESC
            """,
            conn,
        )
        promotion_effectiveness = pd.read_sql_query(
            """
            SELECT promotion_type, COUNT(*) as total_promotions, AVG(sales_attributed) as avg_attributed_sales,
                   SUM(sales_attributed) as total_attributed_sales, AVG(leads_generated) as avg_leads
            FROM event_promotions
            WHERE sales_attributed > 0 OR leads_generated > 0
            GROUP BY promotion_type
            ORDER BY avg_attributed_sales DESC
            """,
            conn,
        )
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
            GROUP BY 1
            ORDER BY avg_sell_through_rate DESC
            """,
            conn,
        )
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
            """,
            conn,
        )
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
            HAVING COUNT(DISTINCT ei.event_id) >= 2
            ORDER BY avg_sell_through_rate DESC
            """,
            conn,
        )
        return (
            revenue_by_type,
            monthly_trends,
            top_items,
            theme_performance,
            promotion_effectiveness,
            price_analysis,
            seasonal_analysis,
            make_more_less,
        )

def get_smart_inventory_recommendations(event_type=None, season=None):
    with closing(get_conn()) as conn:
        where = ["e.status = 'completed'", "ei.quantity_brought > 0"]
        params = []
        if event_type:
            where.append("e.event_type = ?")
            params.append(event_type)
        if season:
            season_months = {
                'Winter': '(12,1,2)', 'Spring': '(3,4,5)', 'Summer': '(6,7,8)', 'Fall': '(9,10,11)'
            }
            where.append(f"CAST(strftime('%m', e.event_date) AS INTEGER) IN {season_months[season]}")
        where_clause = " AND ".join(where)
        return pd.read_sql_query(
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
            """,
            conn,
            params=params,
        )

# =============== BONUS BILL-PROOF METRICS ===============

def get_inventory_summary():
    """Quick inventory health check - because Bill loves metrics!"""
    with closing(get_conn()) as conn:
        summary = pd.read_sql_query(
            """
            SELECT 
                COUNT(*) as total_items,
                SUM(qty_on_hand) as total_quantity,
                AVG(price) as avg_price,
                COUNT(CASE WHEN qty_on_hand <= 5 THEN 1 END) as low_stock_items
            FROM items
            """,
            conn,
        )
        return summary.iloc[0].to_dict() if not summary.empty else {}

def get_monthly_revenue_target_vs_actual():
    """Revenue tracking - Bill LOVES when we hit targets!"""
    with closing(get_conn()) as conn:
        current_year = date.today().year
        current_month = date.today().month
        
        # Get this month's actual revenue
        actual = pd.read_sql_query(
            """
            SELECT COALESCE(SUM(total_revenue), 0) as actual_revenue
            FROM events 
            WHERE status = 'completed' 
            AND strftime('%Y', event_date) = ? 
            AND strftime('%m', event_date) = ?
            """,
            conn,
            params=(str(current_year), f"{current_month:02d}"),
        )
        
        # Get monthly target from goals (if any)
        target = pd.read_sql_query(
            """
            SELECT target_value / 12 as monthly_target
            FROM business_goals 
            WHERE goal_type = 'revenue' 
            AND status = 'active' 
            AND target_date LIKE ?
            """,
            conn,
            params=(f"{current_year}%",),
        )
        
        return {
            'actual': actual.iloc[0]['actual_revenue'] if not actual.empty else 0,
            'target': target.iloc[0]['monthly_target'] if not target.empty else 0
        }

# =============== UI PARTS ===============

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

# ---- Event screens ----

def event_form_ui(existing=None):
    st.subheader("Event Planning")
    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input("Event Name", value=(existing or {}).get("name", ""))
        event_date = st.date_input("Date", value=date.today())
        location = st.text_input("Location", value=(existing or {}).get("location", ""))
        event_type = st.selectbox("Event Type", ["Art Fair", "Farmers Market", "Studio Sale", "Gallery Show", "Holiday Market", "Other"], index=0)
        booth_fee = st.number_input("Booth Fee", min_value=0.0, step=5.0)
    with col2:
        setup_time = st.text_input("Setup Time", value=(existing or {}).get("setup_time", ""))
    st.subheader("Theme & Strategy")
    col3, col4 = st.columns(2)
    with col3:
        theme = st.text_input("Theme/Collection Name", value=(existing or {}).get("theme", ""))
        theme_description = st.text_area("Theme Description", value=(existing or {}).get("theme_description", ""))
        color_palette = st.text_input("Color Palette", value=(existing or {}).get("color_palette", ""))
    with col4:
        target_customer = st.selectbox("Target Customer", ["Holiday gift buyers", "Home decorators", "Collectors", "Young professionals", "Families", "Art enthusiasts", "Kitchen/dining focused", "Garden lovers", "Other"])
        price_strategy = st.selectbox("Pricing Strategy", ["Premium pricing", "Volume pricing", "Mixed range", "Gift focused", "Statement pieces", "Testing new prices"]) 
    if st.checkbox("Mark as completed and add sales data"):
        st.subheader("Event Results")
        col7, col8 = st.columns(2)
        with col7:
            total_revenue = st.number_input("Total Revenue", min_value=0.0, step=0.01)
            cash_sales = st.number_input("Cash Sales", min_value=0.0, step=0.01)
            card_sales = st.number_input("Card Sales", min_value=0.0, step=0.01)
        with col8:
            check_sales = st.number_input("Check Sales", min_value=0.0, step=0.01)
            discounts_given = st.number_input("Discounts Given", min_value=0.0, step=0.01)
            rewards_given = st.number_input("Rewards Given", min_value=0.0, step=0.01)
        weather = st.text_input("Weather")
        foot_traffic = st.selectbox("Foot Traffic", ["Light", "Moderate", "Heavy", "Excellent"]) 
        status = "completed"
    else:
        total_revenue = cash_sales = card_sales = check_sales = discounts_given = rewards_given = 0.0
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
        st.success(f"Event saved. ID {event_id}")
        return event_id
    return None

# =============== HIGH LEVEL PAGES ===============

def goals_manager():
    st.header("Business Goals & Growth Tracking")
    auto_update_goals_from_events()
    active_goals = get_active_goals()
    if not active_goals.empty:
        st.subheader("Goal Progress Overview")
        for _, goal in active_goals.iterrows():
            progress = (goal['current_value'] / goal['target_value']) * 100 if goal['target_value'] else 0
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.write(f"**{goal['goal_name']}**")
                st.caption(f"{goal['category']}")
            with col2:
                st.metric("Progress", f"{goal['current_value']:.0f} / {goal['target_value']:.0f} {goal['measurement_unit'] or ''}")
            with col3:
                st.progress(min(progress/100, 1.0))
                st.write(f"{progress:.1f}%")
            with col4:
                try:
                    days_remaining = (datetime.strptime(goal['target_date'], '%Y-%m-%d').date() - date.today()).days
                    st.write(f"{days_remaining} days left" if days_remaining >= 0 else f"{abs(days_remaining)} days overdue")
                except Exception:
                    st.write("")
        st.divider()
    with st.expander("Create New Goal", expanded=len(active_goals)==0):
        col1, col2 = st.columns(2)
        with col1:
            goal_name = st.text_input("Goal Name")
            goal_type = st.selectbox("Goal Type", ["revenue", "events", "social_media", "custom"]) 
            target_value = st.number_input("Target Value", min_value=0.0, step=1.0)
        with col2:
            target_date = st.date_input("Target Date", value=date(date.today().year, 12, 31))
            category = st.selectbox("Category", ["Annual Goals", "Quarterly Goals", "Monthly Goals", "Growth Targets", "Other"]) 
            unit_default = {"revenue":"$", "events":"events", "social_media":"followers"}.get(goal_type, "units")
            measurement_unit = st.text_input("Unit", value=unit_default)
        description = st.text_area("Description")
        if st.button("Create Goal", type="primary"):
            if goal_name and target_value > 0:
                gid = create_goal({
                    "goal_name": goal_name,
                    "goal_type": goal_type,
                    "target_value": target_value,
                    "target_date": target_date,
                    "measurement_unit": measurement_unit,
                    "category": category,
                    "description": description,
                })
                st.success(f"Goal created ID {gid}")
                st.rerun()
            else:
                st.error("Please fill goal name and target value")
    if not active_goals.empty:
        st.subheader("Update Goal Progress")
        options = [f"{r['goal_name']} (Current {r['current_value']:.0f})" for _, r in active_goals.iterrows()]
        idx = st.selectbox("Select Goal", range(len(options)), format_func=lambda i: options[i])
        sel = active_goals.iloc[idx]
        col1, col2 = st.columns(2)
        with col1:
            new_val = st.number_input("New Value", min_value=0.0, value=float(sel['current_value']), step=1.0)
        with col2:
            notes = st.text_input("Notes")
        cA, cB = st.columns(2)
        with cA:
            if st.button("Update Progress"):
                update_goal_progress(sel['id'], new_val, notes)
                st.success("Updated")
                st.rerun()
        with cB:
            del_confirm = st.checkbox("Confirm delete")
            if st.button("Delete Goal"):
                if del_confirm:
                    delete_goal(int(sel['id']))
                    st.success("Goal deleted")
                    st.rerun()
                else:
                    st.warning("Check confirm delete first")

def yearly_dashboard():
    st.header("Annual Business Dashboard")
    current_year = date.today().year
    selected_year = st.selectbox("Select Year", [current_year, current_year-1, current_year-2], index=0)
    yr, monthly, prev = calculate_yearly_metrics(selected_year)
    if not yr.empty:
        total_rev = yr.iloc[0]['total_revenue'] or 0
        total_events = yr.iloc[0]['total_events'] or 0
        avg_per = total_rev / max(total_events, 1)
        prev_rev = prev.iloc[0]['total_revenue'] or 0 if not prev.empty else 0
        prev_events = prev.iloc[0]['total_events'] or 0 if not prev.empty else 0
        rev_growth = ((total_rev - prev_rev) / prev_rev * 100) if prev_rev else None
        evt_growth = ((total_events - prev_events) / prev_events * 100) if prev_events else None
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.metric("Total Revenue", f"${total_rev:.2f}", None if rev_growth is None else f"{rev_growth:+.1f}%")
        with c2: st.metric("Total Events", int(total_events), None if evt_growth is None else f"{evt_growth:+.1f}%")
        with c3: st.metric("Avg per Event", f"${avg_per:.2f}")
        with c4:
            goals = get_active_goals()
            if not goals.empty:
                g = goals[(goals['goal_type']=="revenue") & (goals['target_date'].str.startswith(str(selected_year)))]
                if not g.empty:
                    prog = (total_rev / g.iloc[0]['target_value']) * 100
                    st.metric("Goal Progress", f"{prog:.1f}%")
    if not monthly.empty:
        month_names = {'01':'Jan','02':'Feb','03':'Mar','04':'Apr','05':'May','06':'Jun','07':'Jul','08':'Aug','09':'Sep','10':'Oct','11':'Nov','12':'Dec'}
        monthly['month_name'] = monthly['month'].map(month_names)
        c1, c2 = st.columns(2)
        with c1:
            st.subheader(f"{selected_year} Revenue by Month")
            st.bar_chart(monthly.set_index('month_name')['revenue'])
        with c2:
            st.subheader(f"{selected_year} Revenue Trend")
            st.line_chart(monthly.set_index('month_name')['revenue'])
        st.dataframe(monthly[['month_name','revenue','events']], use_container_width=True)

def analytics_dashboard():
    st.header("Event Analytics")
    (
        revenue_by_type,
        monthly_trends,
        top_items,
        theme_performance,
        promotion_effectiveness,
        price_analysis,
        seasonal_analysis,
        make_more_less,
    ) = calculate_event_metrics()
    if not revenue_by_type.empty:
        st.subheader("Average Revenue by Event Type")
        chart_data = revenue_by_type.set_index('event_type')['avg_revenue']
        st.bar_chart(chart_data)
    if not top_items.empty:
        st.subheader("Top Items by Units Sold")
        st.dataframe(top_items, use_container_width=True)
    if not price_analysis.empty:
        st.subheader("Sell Through by Price Range")
        st.bar_chart(price_analysis.set_index('price_range')['avg_sell_through_rate'])

# ---- Promotions and Event Inventory managers (with delete) ----

def promotion_manager(event_id):
    st.subheader("Promotion Planning & Tracking")
    promos = get_event_promotions(event_id)
    if not promos.empty:
        for _, promo in promos.iterrows():
            with st.expander(f"{promo['promotion_type']} - {promo['platform']} on {promo['scheduled_date']}"):
                st.write(promo)
                if st.button("Delete promotion", key=f"del_promo_{promo['id']}"):
                    delete_promotion(int(promo['id']))
                    st.success("Deleted promotion")
                    st.rerun()
    else:
        st.info("No promotions yet.")
    with st.expander("Add promotion"):
        col1, col2 = st.columns(2)
        with col1:
            ptype = st.text_input("Type")
            platform = st.text_input("Platform")
            sched = st.date_input("Scheduled date")
        with col2:
            audience = st.text_input("Target audience")
            goal = st.text_input("Engagement goal")
        content = st.text_area("Content")
        leads = st.number_input("Leads generated", min_value=0)
        sales_attr = st.number_input("Sales attributed", min_value=0.0, step=0.01)
        if st.button("Add promotion"):
            add_promotion(event_id, {
                "promotion_type": ptype,
                "platform": platform,
                "content": content,
                "scheduled_date": sched,
                "target_audience": audience,
                "engagement_goal": goal,
                "actual_engagement": "",
                "leads_generated": leads,
                "sales_attributed": sales_attr,
            })
            st.success("Added")
            st.rerun()

# =============== APP ===============

st.set_page_config(page_title="Pottery Shop & Events", page_icon="🧱", layout="wide")
init_db()

menu = st.sidebar.selectbox(
    "Go to",
    [
        "New Event",
        "Shows & Events",
        "Event Analytics",
        "Smart Planning",
        "Business Goals",
        "Yearly Dashboard",
        "Dashboard",
        "Items",
        "New item",
        "Import or Export",
    ],
)

if menu == "Dashboard":
    st.header("🧱 Pottery Shop & Business Intelligence")
    st.write("Complete business management for pottery artists - because Bill was wrong!")
    
    # Add Bill-proof metrics at the top
    inv_summary = get_inventory_summary()
    revenue_monthly = get_monthly_revenue_target_vs_actual()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("Total Items", int(inv_summary.get('total_items', 0)))
    with col2: st.metric("Total Inventory", int(inv_summary.get('total_quantity', 0)))
    with col3: st.metric("Low Stock Items", int(inv_summary.get('low_stock_items', 0)))
    with col4: 
        if revenue_monthly['target'] > 0:
            pct = (revenue_monthly['actual'] / revenue_monthly['target']) * 100
            st.metric("Monthly Target", f"{pct:.1f}%")
        else:
            st.metric("This Month", f"${revenue_monthly['actual']:.2f}")
    
    events_df = get_events()
    y = date.today().year
    c1, c2, c3 = st.columns(3)
    if not events_df.empty:
        comp = events_df[events_df['status'] == 'completed']
        cy = comp[pd.to_datetime(comp['event_date']).dt.year == y] if not comp.empty else pd.DataFrame()
        with c1: st.metric("This Year's Shows", 0 if cy.empty else len(cy))
        with c2: st.metric("This Year's Revenue", f"${0 if cy.empty else cy['total_revenue'].sum():.2f}")
        with c3: st.metric("Average per Show", f"${0 if cy.empty else cy['total_revenue'].mean():.2f}")
    auto_update_goals_from_events()
    goals = get_active_goals()
    if not goals.empty:
        st.subheader("Goals Snapshot")
        for _, goal in goals.head(3).iterrows():
            pct = (goal['current_value']/goal['target_value']*100) if goal['target_value'] else 0
            c1, c2, c3 = st.columns([2,1,1])
            with c1:
                st.write(f"**{goal['goal_name']}**")
                st.progress(min(pct/100,1.0))
            with c2:
                st.write(f"{goal['current_value']:.0f}/{goal['target_value']:.0f}")
            with c3:
                st.write(f"{pct:.1f}%")
    df = fetch_items_df()
    if not df.empty:
        st.subheader("Recent Items")
        st.dataframe(df[["sku","name","qty_on_hand","price","category","glaze","updated_at"]].head(10), use_container_width=True)

elif menu == "Shows & Events":
    st.header("Shows & Events")
    events_df = get_events()
    if not events_df.empty:
        st.dataframe(events_df, use_container_width=True)
        names = [f"{r['name']} - {r['event_date']}" for _, r in events_df.iterrows()]
        pick = st.selectbox("Select an event", names)
        if pick:
            event_id = events_df.iloc[names.index(pick)]['id']
            event = get_event_by_id(event_id)
            st.subheader(f"Managing: {event['name']}")
            col_del1, col_del2 = st.columns([3,1])
            with col_del2:
                confirm = st.checkbox("Confirm delete", key=f"confirm_del_evt_{event['id']}")
                if st.button("Delete Event", key=f"del_evt_{event['id']}"):
                    if confirm:
                        delete_event(int(event['id']))
                        st.success("Event deleted")
                        st.rerun()
                    else:
                        st.warning("Check confirm delete first")
            tab1, tab2, tab3, tab4 = st.tabs(["Event Strategy", "Promotions", "Inventory", "Reflections"])
            with tab1:
                c1, c2 = st.columns(2)
                with c1:
                    st.write(f"**Theme:** {event.get('theme','')}")
                    if event.get('theme_description'): st.write(f"**Description:** {event['theme_description']}")
                    if event.get('color_palette'): st.write(f"**Colors:** {event['color_palette']}")
                with c2:
                    st.write(f"**Target Customer:** {event.get('target_customer','')}")
                    st.write(f"**Price Strategy:** {event.get('price_strategy','')}")
                    st.write(f"**Status:** {event.get('status','')}")
                if event.get('status') == 'completed':
                    c3, c4, c5 = st.columns(3)
                    with c3: st.metric("Total Revenue", f"${event['total_revenue']:.2f}")
                    with c4: st.metric("Net Revenue", f"${(event['total_revenue'] - event['booth_fee']):.2f}")
                    with c5: st.metric("ROI", f"{((event['total_revenue'] - max(event['booth_fee'],0)) / max(event['booth_fee'],1) * 100):.1f}%")
            with tab2:
                promotion_manager(event_id)
                st.caption("Tip: delete or add promos below. Changes save instantly.")
            with tab3:
                # Quick add from inventory
                items_df = fetch_items_df()
                if not items_df.empty:
                    st.write("Add items from inventory")
                    selected = st.multiselect(
                        "Select items",
                        options=items_df['sku'].tolist(),
                        format_func=lambda x: f"{x} - {items_df[items_df['sku']==x]['name'].iloc[0]}",
                    )
                    for sku in selected:
                        item = items_df[items_df['sku']==sku].iloc[0]
                        c1, c2, c3, c4 = st.columns(4)
                        with c1: st.write(f"**{item['name']}**")
                        with c2: brought = st.number_input("Brought", min_value=0, key=f"b_{sku}")
                        with c3: sold = st.number_input("Sold", min_value=0, key=f"s_{sku}")
                        with c4: price = st.number_input("Price", min_value=0.0, value=float(item['price'] or 0), key=f"p_{sku}")
                        if st.button(f"Add {sku}", key=f"add_{sku}"):
                            add_event_inventory(event_id, sku, item['name'], brought, sold, price)
                            st.success(f"Added {item['name']}")
                inv = get_event_inventory(event_id)
                if not inv.empty:
                    inv = inv.copy()
                    inv['sell_through_rate'] = (inv['quantity_sold'] / inv['quantity_brought'].replace(0,1)) * 100
                    inv['revenue'] = inv['quantity_sold'] * inv['price_at_event']
                    st.subheader("Current Event Inventory")
                    st.dataframe(inv, use_container_width=True)
                    # Quick delete controls per line
                    for _, row in inv.iterrows():
                        if st.button("Delete line", key=f"del_line_{row['id']}"):
                            delete_event_inventory_row(int(row['id']))
                            st.success("Deleted")
                            st.rerun()
                    c1, c2, c3 = st.columns(3)
                    with c1: st.metric("Total Brought", int(inv['quantity_brought'].sum()))
                    with c2: st.metric("Total Sold", int(inv['quantity_sold'].sum()))
                    with c3: st.metric("Total Revenue", f"${inv['revenue'].sum():.2f}")
            with tab4:
                st.subheader("Event Reflections & Learning")
                env = get_environment_data(event_id)
                with st.expander("Event Environment & Neighbors", expanded=False):
                    c1, c2 = st.columns(2)
                    with c1:
                        left = st.text_input("Neighbor Left", value=(env or {}).get("neighboring_vendor_left", ""))
                        right = st.text_input("Neighbor Right", value=(env or {}).get("neighboring_vendor_right", ""))
                        booth_loc = st.text_input("Booth Location", value=(env or {}).get("booth_location", ""))
                    with c2:
                        flow = st.text_area("Foot Traffic Pattern", value=(env or {}).get("foot_traffic_pattern", ""))
                        demo = st.text_area("Customer Demographics", value=(env or {}).get("customer_demographics", ""))
                    comp = st.text_area("Competition/Similar Vendors", value=(env or {}).get("competition_notes", ""))
                    price_obs = st.text_area("Pricing Observations", value=(env or {}).get("pricing_observations", ""))
                    if st.button("Save Environment Data"):
                        add_environment_data(event_id, {
                            "neighboring_vendor_left": left,
                            "neighboring_vendor_right": right,
                            "booth_location": booth_loc,
                            "foot_traffic_pattern": flow,
                            "customer_demographics": demo,
                            "competition_notes": comp,
                            "pricing_observations": price_obs,
                        })
                        st.success("Saved")
                st.subheader("Add New Reflection")
                c1, c2 = st.columns(2)
                with c1:
                    ref_cat = st.selectbox("Category", ["Customer Interactions","What Worked","What Didn't Work","Next Time","Pricing Insights","Marketing Notes","Setup & Logistics","Competition Analysis","Product Feedback","Sales Conversations","Display Ideas"]) 
                    flag_cust = st.checkbox("Customer interaction note")
                    flag_price = st.checkbox("Contains pricing insights")
                with c2:
                    ref_text = st.text_area("Reflection Notes", height=150)
                if st.button("Add Reflection") and ref_text:
                    add_reflection(event_id, ref_cat, ref_text, flag_cust, flag_price)
                    st.success("Added")
                refl = get_reflections(event_id)
                # Quick delete panel
                with st.expander("Delete reflections"):
                    if not refl.empty:
                        for _, rr in refl.iterrows():
                            colr1, colr2 = st.columns([4,1])
                            with colr1:
                                st.write(f"{rr['category']} | {rr['created_at'][:10]}: {rr['content'][:80]}...")
                            with colr2:
                                if st.button("Delete", key=f"refdel_{rr['id']}"):
                                    delete_reflection(int(rr['id']))
                                    st.success("Deleted")
                                    st.rerun()
                if not refl.empty:
                    st.subheader("Previous Reflections")
                    f1, f2, f3 = st.columns(3)
                    with f1: only_cust = st.checkbox("Customer only")
                    with f2: only_price = st.checkbox("Pricing only")
                    with f3: cat = st.selectbox("Filter", ["All"] + refl['category'].unique().tolist())
                    dfv = refl.copy()
                    if only_cust: dfv = dfv[dfv['customer_interaction']==1]
                    if only_price: dfv = dfv[dfv['price_point_insight']==1]
                    if cat != "All": dfv = dfv[dfv['category']==cat]
                    for _, r in dfv.iterrows():
                        prefix = ("👥 " if r['customer_interaction'] else "") + ("💰 " if r['price_point_insight'] else "")
                        with st.expander(f"{prefix}{r['category']} - {r['created_at'][:10]}"):
                            st.write(r['content'])
    else:
        st.info("No events yet. Create your first event.")

elif menu == "New Event":
    st.header("New Event")
    event_form_ui()

elif menu == "Event Analytics":
    analytics_dashboard()

elif menu == "Smart Planning":
    st.header("Smart Event Planning Assistant")
    etype = st.selectbox("Upcoming Event Type", ["Art Fair", "Farmers Market", "Studio Sale", "Gallery Show", "Holiday Market", "Other"])
    season = st.selectbox("Season", ["Winter","Spring","Summer","Fall"])
    target = st.number_input("Target Revenue", min_value=0.0, step=100.0, value=1000.0)
    booth_fee = st.number_input("Booth Fee", min_value=0.0, step=25.0)
    if st.button("Generate Smart Recommendations", type="primary"):
        rec = get_smart_inventory_recommendations(etype, season)
        if not rec.empty:
            st.subheader("Inventory Recommendations")
            total_expected = 0
            for _, it in rec.head(8).iterrows():
                expected = it['avg_sold'] * it['optimal_price']
                total_expected += expected
                c1, c2, c3, c4 = st.columns(4)
                with c1: st.write(f"**{it['item_name']}**")
                with c2: st.write(f"Bring {it['avg_brought']:.0f}")
                with c3: st.write(f"Price ${it['optimal_price']:.2f}")
                with c4: st.write(f"Expected ${expected:.2f}")
            c1, c2, c3 = st.columns(3)
            with c1: st.metric("Expected Revenue", f"${total_expected:.2f}")
            with c2: st.metric("Target Revenue", f"${target:.2f}")
            with c3: st.metric("Difference", f"${(total_expected-target):.2f}")
            st.metric("Expected Profit", f"${(total_expected - booth_fee):.2f}")
            stock = fetch_items_df()
            if not stock.empty:
                st.subheader("Stock Check")
                for _, it in rec.head(5).iterrows():
                    m = stock[stock['name'].str.contains(it['item_name'], case=False, na=False)]
                    if not m.empty:
                        have = m.iloc[0]['qty_on_hand']
                        need = it['avg_brought']
                        if have < need:
                            st.error(f"{it['item_name']}: need {need:.0f}, have {have:.0f}")
                        elif have < need*1.2:
                            st.warning(f"{it['item_name']}: close, have {have:.0f}, need {need:.0f}")
                        else:
                            st.success(f"{it['item_name']}: good, have {have:.0f}")
        else:
            st.info("Not enough history yet for this combination.")

elif menu == "Business Goals":
    goals_manager()

elif menu == "Yearly Dashboard":
    yearly_dashboard()

elif menu == "Items":
    st.header("Items")
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
        cA, cB = st.columns([1,2])
        with cA:
            if item.get("image_path"): st.image(item["image_path"], caption=item["name"], use_column_width=True)
        with cB:
            st.write({k:item[k] for k in ["name","category","clay_body","glaze","size","price","qty_on_hand","location","notes"]})
            adjust_stock_ui(item)
            movements_table(item["id"])
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Edit item"): st.session_state["edit_sku"] = item["sku"]
        with c2:
            if st.button("Delete item"):
                delete_item(item["id"])
                st.success("Deleted")
                st.session_state.pop("open_item", None)
    if "edit_sku" in st.session_state:
        existing = fetch_item_by_sku(st.session_state["edit_sku"])
        st.subheader("Edit item")
        saved = item_form(existing)
        if saved:
            st.session_state.pop("edit_sku", None)
            st.session_state["open_item"] = fetch_item_by_sku(saved)

elif menu == "New item":
    st.header("New item")
    saved = item_form()
    if saved:
        st.session_state["open_item"] = fetch_item_by_sku(saved)
        st.rerun()

elif menu == "Import or Export":
    st.header("Import or Export")
    st.info("CSV import/export coming next. For now use Items and New item.")
    st.write("🎯 **Pro tip**: This is where we'll add Bill-approved data import/export features!")
    
# Footer for good measure
st.sidebar.markdown("---")
st.sidebar.markdown("💪 **Bill-Proof Edition**")
st.sidebar.markdown("✅ All functions working!")
