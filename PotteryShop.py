import streamlit as st
import pandas as pd
import sqlite3
from contextlib import closing
from datetime import datetime, date
import numpy as np

DB_PATH = "pottery_strategy_pro.db"

# =============== CORE BUSINESS FUNCTIONS ===============

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

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        
        # Items table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sku TEXT UNIQUE, name TEXT NOT NULL, category TEXT,
                clay_body TEXT, glaze TEXT, size TEXT, price REAL DEFAULT 0,
                qty_on_hand REAL DEFAULT 0, location TEXT, notes TEXT,
                image_path TEXT, created_at TEXT, updated_at TEXT
            )
        """)
        
        # Stock moves
        cur.execute("""
            CREATE TABLE IF NOT EXISTS stock_moves (
                id INTEGER PRIMARY KEY AUTOINCREMENT, item_id INTEGER NOT NULL,
                move_type TEXT NOT NULL, quantity REAL NOT NULL,
                reference TEXT, moved_at TEXT,
                FOREIGN KEY(item_id) REFERENCES items(id)
            )
        """)
        
        # Events - with the key "change_goal" field
        cur.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
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
        
        # Event inventory
        cur.execute("""
            CREATE TABLE IF NOT EXISTS event_inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER NOT NULL,
                item_sku TEXT NOT NULL, item_name TEXT NOT NULL,
                quantity_brought INTEGER DEFAULT 0, quantity_sold INTEGER DEFAULT 0,
                price_at_event REAL DEFAULT 0, UNIQUE(event_id, item_sku),
                FOREIGN KEY(event_id) REFERENCES events(id)
            )
        """)
        
        # Event reflections
        cur.execute("""
            CREATE TABLE IF NOT EXISTS event_reflections (
                id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER NOT NULL,
                category TEXT NOT NULL, content TEXT NOT NULL,
                customer_interaction INTEGER DEFAULT 0, price_point_insight INTEGER DEFAULT 0,
                created_at TEXT, FOREIGN KEY(event_id) REFERENCES events(id)
            )
        """)
        
        # Event environment
        cur.execute("""
            CREATE TABLE IF NOT EXISTS event_environment (
                id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER NOT NULL UNIQUE,
                neighboring_vendor_left TEXT, neighboring_vendor_right TEXT,
                booth_location TEXT, foot_traffic_pattern TEXT,
                customer_demographics TEXT, competition_notes TEXT,
                pricing_observations TEXT, created_at TEXT,
                FOREIGN KEY(event_id) REFERENCES events(id)
            )
        """)
        
        # Business goals
        cur.execute("""
            CREATE TABLE IF NOT EXISTS business_goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT, goal_name TEXT NOT NULL,
                goal_type TEXT NOT NULL, target_value REAL NOT NULL,
                target_date TEXT NOT NULL, current_value REAL DEFAULT 0,
                measurement_unit TEXT, category TEXT, description TEXT,
                status TEXT DEFAULT 'active', created_at TEXT, updated_at TEXT
            )
        """)
        
        conn.commit()

# =============== DATA FUNCTIONS ===============

def upsert_item(row: dict):
    try:
        with closing(get_conn()) as conn:
            cur = conn.cursor()
            now = datetime.utcnow().isoformat()
            cur.execute("""
                INSERT INTO items (sku, name, category, clay_body, glaze, size, price, qty_on_hand, location, notes, image_path, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(sku) DO UPDATE SET
                    name=excluded.name, category=excluded.category, clay_body=excluded.clay_body,
                    glaze=excluded.glaze, size=excluded.size, price=excluded.price,
                    qty_on_hand=excluded.qty_on_hand, location=excluded.location,
                    notes=excluded.notes, image_path=excluded.image_path, updated_at=?
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
        with closing(get_conn()) as conn:
            if search:
                q = f"%{safe_string(search).strip()}%"
                df = pd.read_sql_query("""
                    SELECT * FROM items
                    WHERE name LIKE ? OR sku LIKE ? OR category LIKE ? OR glaze LIKE ? OR clay_body LIKE ?
                    ORDER BY COALESCE(updated_at, created_at) DESC
                """, conn, params=(q, q, q, q, q))
            else:
                df = pd.read_sql_query("SELECT * FROM items ORDER BY COALESCE(updated_at, created_at) DESC", conn)
            return df
    except Exception as e:
        st.error(f"Database error: {e}")
        return pd.DataFrame()

def fetch_item_by_sku(sku: str):
    try:
        with closing(get_conn()) as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM items WHERE sku = ?", (safe_string(sku),))
            row = cur.fetchone()
            if not row:
                return None
            cols = [c[0] for c in cur.description]
            return dict(zip(cols, row))
    except Exception as e:
        st.error(f"Error fetching item: {e}")
        return None

def record_move(item_id: int, move_type: str, quantity: float, reference: str = ""):
    try:
        with closing(get_conn()) as conn:
            cur = conn.cursor()
            now = datetime.utcnow().isoformat()
            cur.execute("INSERT INTO stock_moves (item_id, move_type, quantity, reference, moved_at) VALUES (?, ?, ?, ?, ?)",
                       (safe_int(item_id), safe_string(move_type), safe_float(quantity), safe_string(reference), now))
            cur.execute("UPDATE items SET qty_on_hand = qty_on_hand + ?, updated_at = ? WHERE id = ?",
                       (safe_float(quantity), now, safe_int(item_id)))
            conn.commit()
    except Exception as e:
        st.error(f"Error recording move: {e}")

def create_event(event_data):
    try:
        with closing(get_conn()) as conn:
            cur = conn.cursor()
            now = datetime.utcnow().isoformat()
            cur.execute("""
                INSERT INTO events (name, event_date, location, event_type, theme, theme_description, change_goal,
                                    color_palette, target_customer, price_strategy, booth_fee, setup_time,
                                    weather, foot_traffic, total_revenue, cash_sales, card_sales, check_sales,
                                    discounts_given, rewards_given, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            event_id = cur.lastrowid
            conn.commit()
            return event_id
    except Exception as e:
        st.error(f"Error creating event: {e}")
        return None

def get_events():
    try:
        with closing(get_conn()) as conn:
            return pd.read_sql_query("SELECT * FROM events ORDER BY event_date DESC", conn)
    except Exception as e:
        st.error(f"Error loading events: {e}")
        return pd.DataFrame()

def get_event_by_id(event_id: int):
    try:
        with closing(get_conn()) as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM events WHERE id = ?", (safe_int(event_id),))
            row = cur.fetchone()
            if not row:
                return None
            cols = [c[0] for c in cur.description]
            return dict(zip(cols, row))
    except Exception as e:
        st.error(f"Error loading event: {e}")
        return None

def add_event_inventory(event_id, sku, name, brought, sold, price):
    try:
        with closing(get_conn()) as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO event_inventory (event_id, item_sku, item_name, quantity_brought, quantity_sold, price_at_event)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(event_id, item_sku) DO UPDATE SET
                    item_name=excluded.item_name,
                    quantity_brought=excluded.quantity_brought,
                    quantity_sold=excluded.quantity_sold,
                    price_at_event=excluded.price_at_event
            """, (safe_int(event_id), safe_string(sku), safe_string(name), 
                  safe_int(brought), safe_int(sold), safe_float(price)))
            conn.commit()
    except Exception as e:
        st.error(f"Error adding event inventory: {e}")

def get_event_inventory(event_id):
    try:
        with closing(get_conn()) as conn:
            return pd.read_sql_query("SELECT * FROM event_inventory WHERE event_id = ?", conn, params=(safe_int(event_id),))
    except Exception as e:
        st.error(f"Error loading event inventory: {e}")
        return pd.DataFrame()

def add_reflection(event_id, category, content, customer_interaction=False, price_point_insight=False):
    try:
        with closing(get_conn()) as conn:
            cur = conn.cursor()
            now = datetime.utcnow().isoformat()
            cur.execute("""
                INSERT INTO event_reflections (event_id, category, content, customer_interaction, price_point_insight, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (safe_int(event_id), safe_string(category), safe_string(content), 
                  int(bool(customer_interaction)), int(bool(price_point_insight)), now))
            conn.commit()
    except Exception as e:
        st.error(f"Error adding reflection: {e}")

def get_reflections(event_id=None):
    try:
        with closing(get_conn()) as conn:
            if event_id:
                return pd.read_sql_query("""
                    SELECT * FROM event_reflections WHERE event_id = ? ORDER BY created_at DESC
                """, conn, params=(safe_int(event_id),))
            else:
                return pd.read_sql_query("""
                    SELECT er.*, e.name as event_name, e.event_date 
                    FROM event_reflections er
                    JOIN events e ON er.event_id = e.id
                    ORDER BY er.created_at DESC
                """, conn)
    except Exception as e:
        st.error(f"Error loading reflections: {e}")
        return pd.DataFrame()

def add_environment_data(event_id, environment_data):
    try:
        with closing(get_conn()) as conn:
            cur = conn.cursor()
            now = datetime.utcnow().isoformat()
            cur.execute("""
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
            """, (safe_int(event_id), safe_string(environment_data.get("neighboring_vendor_left")),
                  safe_string(environment_data.get("neighboring_vendor_right")), safe_string(environment_data.get("booth_location")),
                  safe_string(environment_data.get("foot_traffic_pattern")), safe_string(environment_data.get("customer_demographics")),
                  safe_string(environment_data.get("competition_notes")), safe_string(environment_data.get("pricing_observations")), now))
            conn.commit()
    except Exception as e:
        st.error(f"Error adding environment data: {e}")

def get_environment_data(event_id):
    try:
        with closing(get_conn()) as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM event_environment WHERE event_id = ?", (safe_int(event_id),))
            row = cur.fetchone()
            if not row:
                return None
            cols = [c[0] for c in cur.description]
            return dict(zip(cols, row))
    except Exception as e:
        st.error(f"Error loading environment data: {e}")
        return None

def get_business_insights():
    """Generate business insights for strategic decision making"""
    insights = {}
    
    try:
        with closing(get_conn()) as conn:
            # Price point analysis
            price_analysis = pd.read_sql_query("""
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
            """, conn)
            insights['price_analysis'] = price_analysis
            
            # Make more/less recommendations
            make_more_less = pd.read_sql_query("""
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
            """, conn)
            insights['make_more_less'] = make_more_less
            
            # Seasonal analysis
            seasonal_analysis = pd.read_sql_query("""
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
            """, conn)
            insights['seasonal_analysis'] = seasonal_analysis
            
            # Event type performance
            event_performance = pd.read_sql_query("""
                SELECT event_type, 
                       COUNT(*) as total_events,
                       AVG(total_revenue) as avg_revenue,
                       AVG(total_revenue - booth_fee) as avg_profit,
                       AVG(CASE WHEN booth_fee > 0 THEN total_revenue / booth_fee ELSE NULL END) as avg_roi
                FROM events 
                WHERE status = 'completed'
                GROUP BY event_type
                ORDER BY avg_revenue DESC
            """, conn)
            insights['event_performance'] = event_performance
            
    except Exception as e:
        st.error(f"Error generating insights: {e}")
    
    return insights

# =============== UI COMPONENTS ===============

def strategic_event_planning():
    """Strategic event planning with the key 'What change are you trying to make?' question"""
    st.header("Strategic Event Planning")
    st.markdown("*Plan your creative vision and business strategy*")
    
    # Basic event details
    st.subheader("Event Information")
    col1, col2 = st.columns(2)
    
    with col1:
        name = st.text_input("Event Name")
        event_date = st.date_input("Event Date")
        location = st.text_input("Location")
        event_type = st.selectbox("Event Type", [
            "Art Fair", "Farmers Market", "Studio Sale", "Gallery Show", 
            "Holiday Market", "Pop-up Shop", "Commission Show", "Online Sale", "Other"
        ])
    
    with col2:
        booth_fee = st.number_input("Booth Fee ($)", min_value=0.0, step=25.0)
        setup_time = st.text_input("Setup Time")
        expected_attendance = st.selectbox("Expected Attendance", [
            "Small (< 100)", "Medium (100-500)", "Large (500-1000)", "Very Large (1000+)"
        ])
        revenue_goal = st.number_input("Revenue Goal ($)", min_value=0.0, step=100.0)
    
    # THE KEY QUESTION
    st.subheader("Strategic Intent")
    change_goal = st.text_area("What change are you trying to make?", 
                              placeholder="What do you want to achieve with this event? How does it fit your artistic/business growth? What change in your practice, customer base, or market position are you working toward?",
                              height=100)
    
    # Theme development
    st.subheader("Creative Direction")
    col3, col4 = st.columns(2)
    
    with col3:
        theme_name = st.text_input("Collection/Theme Name")
        theme_description = st.text_area("Theme Description", 
                                        placeholder="Describe the creative vision, story, or concept behind this collection...")
        color_palette = st.text_area("Color Palette & Glazes", 
                                    placeholder="Specific glazes, color combinations, visual mood...")
    
    with col4:
        target_customer = st.text_area("Target Customer", 
                                      placeholder="Who is your ideal customer for this event? What are they looking for?")
        price_strategy = st.text_area("Pricing Strategy", 
                                     placeholder="How will you price for this audience and venue? Any special considerations?")
        unique_value = st.text_area("What Makes Your Work Special?", 
                                   placeholder="What sets your pottery apart? Why should customers choose your work?")
    
    # Event completion tracking
    completed = st.checkbox("Event completed - add results")
    
    if completed:
        st.subheader("Event Results")
        col5, col6 = st.columns(2)
        
        with col5:
            total_revenue = st.number_input("Total Revenue ($)", min_value=0.0, step=0.01)
            cash_sales = st.number_input("Cash Sales ($)", min_value=0.0, step=0.01)
            card_sales = st.number_input("Card Sales ($)", min_value=0.0, step=0.01)
            
        with col6:
            weather_actual = st.text_input("Actual Weather")
            foot_traffic = st.selectbox("Foot Traffic", ["Light", "Moderate", "Heavy", "Excellent"])
            change_achieved = st.text_area("Did you achieve the change you were seeking?", 
                                         placeholder="Reflect on whether you made progress toward your change goal...")
    
    if st.button("Save Event Plan", type="primary"):
        if not name:
            st.error("Please enter an event name")
            return None
        
        event_data = {
            "name": name, "event_date": event_date, "location": location, "event_type": event_type,
            "theme": theme_name, "theme_description": theme_description, "change_goal": change_goal,
            "color_palette": color_palette, "target_customer": target_customer, "price_strategy": price_strategy,
            "booth_fee": booth_fee, "setup_time": setup_time, "weather": weather_actual if completed else "",
            "foot_traffic": foot_traffic if completed else "", "total_revenue": total_revenue if completed else 0,
            "cash_sales": cash_sales if completed else 0, "card_sales": card_sales if completed else 0,
            "check_sales": 0, "discounts_given": 0, "rewards_given": 0,
            "status": "completed" if completed else "planned"
        }
        
        event_id = create_event(event_data)
        if event_id:
            st.success(f"Event plan saved successfully (ID: {event_id})")
            if completed and change_achieved:
                # Save the change reflection
                add_reflection(event_id, "Change Achievement", change_achieved, False, False)
            return event_id
    
    return None

def reflection_journal():
    """Post-event reflection and learning capture"""
    st.header("Event Reflection Journal")
    st.markdown("*Capture insights and learnings from your pottery events*")
    
    events_df = get_events()
    
    if events_df.empty:
        st.info("No events found. Create an event first to start journaling.")
        return
    
    # Event selection
    event_options = [f"{row['name']} - {row['event_date']}" for _, row in events_df.iterrows()]
    selected_event = st.selectbox("Select Event to Reflect On", event_options)
    
    if selected_event:
        event_idx = event_options.index(selected_event)
        event = events_df.iloc[event_idx]
        event_id = event['id']
        
        st.subheader(f"Reflecting on: {event['name']}")
        
        # Show event context
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
                    profit = event['total_revenue'] - event['booth_fee']
                    st.write(f"**Profit:** ${profit:.2f}")
        
        # Add new reflection
        st.subheader("Add New Reflection")
        
        col3, col4 = st.columns(2)
        with col3:
            reflection_category = st.selectbox("Reflection Type", [
                "What Worked Well",
                "What Didn't Work", 
                "Customer Interactions & Feedback",
                "Pricing Observations",
                "Display & Setup Insights",
                "Competition & Market Analysis",
                "Next Time Planning",
                "Creative Discoveries",
                "Business Learning",
                "Change Progress"
            ])
            
            customer_interaction = st.checkbox("Customer interaction note")
            price_insight = st.checkbox("Contains pricing insights")
        
        with col4:
            reflection_content = st.text_area("Reflection Content", height=150,
                                            placeholder="What did you observe? What did you learn? How did customers respond? What would you do differently?")
        
        if st.button("Save Reflection") and reflection_content:
            add_reflection(event_id, reflection_category, reflection_content, customer_interaction, price_insight)
            st.success("Reflection saved")
            st.rerun()
        
        # Environment tracking
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
        
        # Show existing reflections
        reflections = get_reflections(event_id)
        
        if not reflections.empty:
            st.subheader("Previous Reflections")
            
            # Filter options
            col7, col8, col9 = st.columns(3)
            with col7:
                filter_category = st.selectbox("Filter by Type", 
                                             ["All"] + list(reflections['category'].unique()))
            with col8:
                show_customer_only = st.checkbox("Customer interactions only")
            with col9:
                show_pricing_only = st.checkbox("Pricing insights only")
            
            # Apply filters
            filtered_reflections = reflections.copy()
            if filter_category != "All":
                filtered_reflections = filtered_reflections[filtered_reflections['category'] == filter_category]
            if show_customer_only:
                filtered_reflections = filtered_reflections[filtered_reflections['customer_interaction'] == 1]
            if show_pricing_only:
                filtered_reflections = filtered_reflections[filtered_reflections['price_point_insight'] == 1]
            
            # Display reflections
            for _, reflection in filtered_reflections.iterrows():
                date_str = reflection['created_at'][:10] if reflection['created_at'] else ""
                
                flags = []
                if reflection['customer_interaction']:
                    flags.append("👥 Customer")
                if reflection['price_point_insight']:
                    flags.append("💰 Pricing")
                flag_str = " | ".join(flags)
                
                title = f"{reflection['category']} - {date_str}"
                if flag_str:
                    title += f" | {flag_str}"
                
                with st.expander(title):
                    st.write(reflection['content'])

def business_insights_dashboard():
    """Strategic business insights for decision making"""
    st.header("Business Insights Dashboard")
    st.markdown("*Data-driven insights for strategic pottery business decisions*")
    
    insights = get_business_insights()
    
    if not insights or all(df.empty for df in insights.values()):
        st.info("Complete some events with inventory tracking to see business insights.")
        return
    
    # Price point analysis
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
            
            st.markdown("**Strategic Recommendation:**")
            if best_range['avg_sell_through_rate'] > 0.7:
                st.success(f"Focus more inventory in the {best_range['price_range']} range - strong demand!")
            else:
                st.info(f"Consider experimenting with pricing in the {best_range['price_range']} range")
        
        st.dataframe(price_df, use_container_width=True)
    
    # Production recommendations
    if 'make_more_less' in insights and not insights['make_more_less'].empty:
        st.subheader("Production Strategy Recommendations")
        recs_df = insights['make_more_less']
        
        make_more = recs_df[recs_df['recommendation'] == 'MAKE MORE']
        make_less = recs_df[recs_df['recommendation'] == 'MAKE LESS']
        review = recs_df[recs_df['recommendation'] == 'REVIEW']
        
        col3, col4, col5 = st.columns(3)
        
        with col3:
            st.markdown("**🟢 MAKE MORE**")
            st.caption("High demand items (>80% sell-through)")
            if not make_more.empty:
                for _, item in make_more.iterrows():
                    st.write(f"• **{item['item_name']}** - {item['avg_sell_through_rate']:.1%}")
            else:
                st.write("No high-demand items yet")
        
        with col4:
            st.markdown("**🟡 REVIEW**")
            st.caption("Moderate performance (20-80% sell-through)")
            if not review.empty:
                for _, item in review.head(3).iterrows():
                    st.write(f"• **{item['item_name']}** - {item['avg_sell_through_rate']:.1%}")
        
        with col5:
            st.markdown("**🔴 MAKE LESS**")
            st.caption("Lower demand items (<20% sell-through)")
            if not make_less.empty:
                for _, item in make_less.iterrows():
                    st.write(f"• **{item['item_name']}** - {item['avg_sell_through_rate']:.1%}")
            else:
                st.write("All items performing well!")
        
        st.dataframe(recs_df[['item_name', 'events_brought_to', 'avg_sell_through_rate', 'total_revenue', 'recommendation']], 
                    use_container_width=True)
    
    # Seasonal analysis
    if 'seasonal_analysis' in insights and not insights['seasonal_analysis'].empty:
        st.subheader("Seasonal Performance Trends")
        seasonal_df = insights['seasonal_analysis']
        
        st.markdown("**Top performers by season:**")
        for season in ['Spring', 'Summer', 'Fall', 'Winter']:
            season_data = seasonal_df[seasonal_df['season'] == season]
            if not season_data.empty:
                with st.expander(f"{season} - Top Items"):
                    top_items = season_data.head(5)
                    for _, item in top_items.iterrows():
                        st.write(f"• **{item['item_name']}** - {item['total_sold']} sold, ${item['avg_price']:.2f} avg, {item['avg_sell_through_rate']:.1%} sell-through")
    
    # Event type performance
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
    """Inventory tracking and management"""
    st.header("Inventory Management")
    st.markdown("*Track your pottery pieces and stock levels*")
    
    # Search and add new item
    col1, col2 = st.columns([3, 1])
    with col1:
        search_query = st.text_input("Search inventory", placeholder="Search by name, SKU, category, glaze...")
    with col2:
        if st.button("Add New Item", type="primary"):
            st.session_state['show_item_form'] = True
    
    # Add new item form
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
                    item_data = {
                        "sku": sku, "name": name, "category": category, "clay_body": clay_body,
                        "glaze": glaze, "size": size, "price": price, "qty_on_hand": qty_on_hand,
                        "location": location, "notes": notes
                    }
                    upsert_item(item_data)
                    st.success("Item saved successfully")
                    st.session_state['show_item_form'] = False
                    st.rerun()
                else:
                    st.error("SKU and Name are required")
        
        with col6:
            if st.button("Cancel"):
                st.session_state['show_item_form'] = False
                st.rerun()
    
    # Display inventory
    items_df = fetch_items_df(search_query)
    
    if not items_df.empty:
        st.subheader("Current Inventory")
        
        # Summary metrics
        col7, col8, col9, col10 = st.columns(4)
        with col7:
            st.metric("Total Items", len(items_df))
        with col8:
            st.metric("Total Pieces", int(items_df['qty_on_hand'].sum()))
        with col9:
            st.metric("Total Value", f"${(items_df['qty_on_hand'] * items_df['price']).sum():.2f}")
        with col10:
            low_stock = len(items_df[items_df['qty_on_hand'] <= 5])
            st.metric("Low Stock Items", low_stock)
        
        # Inventory table
        display_cols = ['sku', 'name', 'category', 'clay_body', 'glaze', 'price', 'qty_on_hand', 'location']
        st.dataframe(items_df[display_cols], use_container_width=True)
        
        # Stock adjustment
        if not items_df.empty:
            st.subheader("Stock Adjustment")
            item_names = [f"{row['sku']} - {row['name']}" for _, row in items_df.iterrows()]
            selected_item = st.selectbox("Select item to adjust", item_names)
            
            if selected_item:
                item_idx = item_names.index(selected_item)
                item = items_df.iloc[item_idx]
                
                col11, col12 = st.columns(2)
                with col11:
                    quantity_change = st.number_input("Quantity change", value=0.0, step=1.0, 
                                                    help="Positive for adding stock, negative for removing")
                with col12:
                    reference = st.text_input("Reference/Reason", placeholder="e.g., 'Completed firing', 'Sold at market'")
                
                if st.button("Record Stock Movement") and quantity_change != 0:
                    record_move(item['id'], "adjustment", quantity_change, reference)
                    st.success("Stock movement recorded")
                    st.rerun()
    
    else:
        st.info("No inventory items found. Add your first item to get started.")

def event_management():
    """Event management and inventory tracking"""
    st.header("Events & Show Management")
    st.markdown("*Manage your events and track what you bring and sell*")
    
    events_df = get_events()
    
    if events_df.empty:
        st.info("No events found. Use 'Strategic Event Planning' to create your first event.")
        return
    
    # Event selection
    event_options = [f"{row['name']} - {row['event_date']}" for _, row in events_df.iterrows()]
    selected_event = st.selectbox("Select Event to Manage", event_options)
    
    if selected_event:
        event_idx = event_options.index(selected_event)
        event = events_df.iloc[event_idx]
        event_id = event['id']
        
        st.subheader(f"Managing: {event['name']}")
        
        # Event summary
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
                profit = event['total_revenue'] - event['booth_fee']
                st.write(f"**Profit:** ${profit:.2f}")
        
        # Inventory management for this event
        st.subheader("Event Inventory")
        
        # Add items to event
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
        
        # Show current event inventory
        event_inventory = get_event_inventory(event_id)
        if not event_inventory.empty:
            st.markdown("**Current Event Inventory:**")
            
            # Calculate metrics
            event_inventory = event_inventory.copy()
            event_inventory['sell_through_rate'] = (event_inventory['quantity_sold'] / 
                                                   event_inventory['quantity_brought'].replace(0, 1)) * 100
            event_inventory['revenue'] = event_inventory['quantity_sold'] * event_inventory['price_at_event']
            
            st.dataframe(event_inventory, use_container_width=True)
            
            # Summary metrics
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

# Add these functions to your PotteryShop.py file after the existing database helper functions

def delete_goal(goal_id):
    """Delete a business goal and all its related progress/milestones"""
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        # Delete related records first
        cur.execute("DELETE FROM goal_progress WHERE goal_id = ?", (goal_id,))
        cur.execute("DELETE FROM goal_milestones WHERE goal_id = ?", (goal_id,))
        # Delete the goal itself
        cur.execute("DELETE FROM business_goals WHERE id = ?", (goal_id,))
        conn.commit()

def delete_promotion(promotion_id):
    """Delete an event promotion"""
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM event_promotions WHERE id = ?", (promotion_id,))
        conn.commit()

def delete_event_inventory_row(inventory_id):
    """Delete a single event inventory line item"""
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM event_inventory WHERE id = ?", (inventory_id,))
        conn.commit()

def delete_reflection(reflection_id):
    """Delete an event reflection"""
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM event_reflections WHERE id = ?", (reflection_id,))
        conn.commit()

def delete_event(event_id):
    """Delete an event and all related data"""
    with closing(get_conn()) as conn:
        cur = conn.cursor()
        # Delete all related records first (foreign key constraints)
        cur.execute("DELETE FROM event_promotions WHERE event_id = ?", (event_id,))
        cur.execute("DELETE FROM event_inventory WHERE event_id = ?", (event_id,))
        cur.execute("DELETE FROM event_reflections WHERE event_id = ?", (event_id,))
        cur.execute("DELETE FROM event_environment WHERE event_id = ?", (event_id,))
        # Finally delete the event itself
        cur.execute("DELETE FROM events WHERE id = ?", (event_id,))
        conn.commit()

# =============== MAIN APPLICATION ===============

st.set_page_config(
    page_title="Pottery Strategy Pro", 
    page_icon="🏺", 
    layout="wide"
)

# Professional styling
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #8B4513, #D2B48C);
        padding: 20px;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 30px;
    }
    .stMetric > div[data-testid="metric-container"] {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .stButton > button {
        background-color: #8B4513;
        color: white;
        border-radius: 8px;
        border: none;
        padding: 12px 24px;
        font-weight: 500;
    }
    .stButton > button:hover {
        background-color: #A0522D;
    }
</style>
""", unsafe_allow_html=True)

# Initialize database
try:
    init_db()
except Exception as e:
    st.error(f"Database initialization error: {e}")
    st.stop()

# Header
st.markdown("""
<div class="main-header">
    <h1>🏺 Pottery Strategy Pro</h1>
    <p>Strategic planning and business insights for pottery artists</p>
</div>
""", unsafe_allow_html=True)

# Navigation
st.sidebar.title("Navigation")
menu_options = [
    "Strategic Event Planning",
    "Dashboard", 
    "Event Reflection Journal",
    "Business Insights",
    "Event Management",
    "Inventory Management"
]

menu = st.sidebar.selectbox("Go to", menu_options)

# Initialize session state
if 'show_item_form' not in st.session_state:
    st.session_state['show_item_form'] = False

# Main content
if menu == "Strategic Event Planning":
    strategic_event_planning()

elif menu == "Dashboard":
    st.header("Overview Dashboard")
    
    # Quick stats
    try:
        with closing(get_conn()) as conn:
            stats = pd.read_sql_query("""
                SELECT 
                    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_events,
                    COUNT(CASE WHEN status = 'planned' THEN 1 END) as planned_events,
                    COALESCE(SUM(CASE WHEN status = 'completed' THEN total_revenue ELSE 0 END), 0) as total_revenue,
                    COALESCE(AVG(CASE WHEN status = 'completed' THEN total_revenue ELSE NULL END), 0) as avg_revenue
                FROM events
            """, conn)
            
            items_count = pd.read_sql_query("SELECT COUNT(*) as count FROM items", conn)
            
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
    
    # Recent activity
    st.subheader("Recent Activity")
    
    # Recent events
    recent_events = get_events().head(5)
    if not recent_events.empty:
        st.markdown("**Recent Events:**")
        for _, event in recent_events.iterrows():
            status_icon = "✅" if event['status'] == 'completed' else "📅"
            st.write(f"{status_icon} **{event['name']}** - {event['event_date']} ({event['status']})")
    
    # Recent reflections
    recent_reflections = get_reflections().head(3)
    if not refl.empty:
    st.subheader("Previous Reflections")
    for _, reflection in refl.iterrows():
        # Note: Using 'category' since 'event_name' doesn't exist in the reflections table
        with st.expander(f"{reflection['category']} - {reflection['created_at'][:10]}"):
            st.write(reflection['content'])
            # Add any additional reflection details here

elif menu == "Dashboard":
    st.header("Overview Dashboard")
    
    # Quick stats
    try:
        with closing(get_conn()) as conn:
            stats = pd.read_sql_query("""
                SELECT 
                    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_events,
                    COUNT(CASE WHEN status = 'planned' THEN 1 END) as planned_events,
                    COALESCE(SUM(CASE WHEN status = 'completed' THEN total_revenue ELSE 0 END), 0) as total_revenue,
                    COALESCE(AVG(CASE WHEN status = 'completed' THEN total_revenue ELSE NULL END), 0) as avg_revenue
                FROM events
            """, conn)
            
            items_count = pd.read_sql_query("SELECT COUNT(*) as count FROM items", conn)
            
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
    
    # Recent activity
    st.subheader("Recent Activity")
    
    # Recent events
    recent_events = get_events().head(5)
    if not recent_events.empty:
        st.markdown("**Recent Events:**")
        for _, event in recent_events.iterrows():
            status_icon = "✅" if event['status'] == 'completed' else "📅"
            st.write(f"{status_icon} **{event['name']}** - {event['event_date']} ({event['status']})")
    
    # Recent reflections
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

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("### Pottery Strategy Pro")
st.sidebar.markdown("*Strategic planning and business insights for pottery artists*")
st.sidebar.markdown("Focus on your craft, grow your business")
