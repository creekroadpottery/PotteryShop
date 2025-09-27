import streamlit as st
import pandas as pd
import sqlite3
from contextlib import closing
from datetime import datetime, date, timedelta
import random

DB_PATH = "pottery_shop.db"

# =============== ENGAGEMENT & FUN HELPERS ===============

def pottery_celebration():
    """Show random celebration messages for achievements!"""
    celebrations = [
        "🎉 Wheel-y awesome work!", "🏺 You're kiln-ing it!", "✨ Clay-some achievement!",
        "🎨 That's some beautiful work!", "💫 Fired up for success!", "🌟 You've got the magic touch!",
        "🎊 Throwing some serious success!", "💎 Pure pottery gold!", "🔥 Hot out of the kiln!",
        "🏆 Master potter vibes!", "🎯 On target!", "⚡ Electric performance!"
    ]
    return random.choice(celebrations)

def pottery_emoji_for_category(category):
    """Return fun emojis for different pottery categories"""
    if not category:
        return '🏺'
    category_lower = str(category).lower()
    emoji_map = {
        'bowl': '🥣', 'mug': '☕', 'cup': '🫖', 'plate': '🍽️', 'dish': '🍽️',
        'vase': '🏺', 'plant': '🪴', 'pot': '🪴', 'decorative': '🎨',
        'functional': '🏠', 'kitchen': '🍽️', 'garden': '🌱', 'sculpture': '🗿'
    }
    for key, emoji in emoji_map.items():
        if key in category_lower:
            return emoji
    return '🏺'

def get_pottery_insights():
    """Generate fun, actionable insights for potters"""
    insights = []
    
    try:
        with closing(get_conn()) as conn:
            # Best selling item this month
            current_month = date.today().replace(day=1)
            best_seller = pd.read_sql_query("""
                SELECT ei.item_name, SUM(ei.quantity_sold) as sold
                FROM event_inventory ei
                JOIN events e ON ei.event_id = e.id
                WHERE e.event_date >= ? AND e.status = 'completed'
                GROUP BY ei.item_name
                ORDER BY sold DESC
                LIMIT 1
            """, conn, params=(current_month.isoformat(),))
            
            if not best_seller.empty:
                item = safe_string(best_seller.iloc[0]['item_name'])
                sold = safe_int(best_seller.iloc[0]['sold'])
                insights.append({
                    'type': 'success', 'icon': '🌟', 'title': 'This Month\'s Superstar!',
                    'message': f"{item} is your champion with {sold} sold! Customers can't get enough!",
                    'action': 'Consider making more of these beauties!'
                })
            
            # Low stock alert
            low_stock = pd.read_sql_query("""
                SELECT name, qty_on_hand FROM items 
                WHERE qty_on_hand <= 3 AND qty_on_hand > 0
                ORDER BY qty_on_hand ASC
            """, conn)
            
            if not low_stock.empty:
                item = safe_string(low_stock.iloc[0]['name'])
                qty = safe_int(low_stock.iloc[0]['qty_on_hand'])
                insights.append({
                    'type': 'warning', 'icon': '🚨', 'title': 'Stock Alert!',
                    'message': f"Only {qty} {item} left in stock!",
                    'action': 'Time to get back to the wheel! 🎯'
                })
            
            # Recent event performance
            recent_event = pd.read_sql_query("""
                SELECT name, total_revenue, event_date FROM events 
                WHERE status = 'completed' 
                ORDER BY event_date DESC LIMIT 1
            """, conn)
            
            if not recent_event.empty:
                event_name = safe_string(recent_event.iloc[0]['name'])
                revenue = safe_float(recent_event.iloc[0]['total_revenue'])
                if revenue > 500:
                    insights.append({
                        'type': 'success', 'icon': '💰', 'title': 'Recent Success!',
                        'message': f"{event_name} brought in ${revenue:.2f}!",
                        'action': 'What made this event special? Document it in reflections!'
                    })
    
    except Exception as e:
        st.error(f"Error getting insights: {e}")
    
    # Seasonal insight
    season_map = {12: 'Winter', 1: 'Winter', 2: 'Winter', 3: 'Spring', 4: 'Spring', 5: 'Spring',
                  6: 'Summer', 7: 'Summer', 8: 'Summer', 9: 'Fall', 10: 'Fall', 11: 'Fall'}
    current_season = season_map[date.today().month]
    season_tips = {
        'Fall': {'icon': '🍂', 'message': 'Perfect time for warm earth tones and cozy mugs!'},
        'Winter': {'icon': '❄️', 'message': 'Holiday season! Gift sets and decorative pieces are hot!'},
        'Spring': {'icon': '🌸', 'message': 'Fresh colors and garden planters are in demand!'},
        'Summer': {'icon': '☀️', 'message': 'Bright colors and outdoor entertaining pieces shine!'}
    }
    
    tip = season_tips[current_season]
    insights.append({
        'type': 'info', 'icon': tip['icon'], 'title': f'{current_season} Vibes',
        'message': tip['message'], 'action': 'Check seasonal recommendations in Smart Planning!'
    })
    
    return insights

def calculate_pottery_level(total_revenue, total_events):
    """Gamification: Calculate potter level based on achievements"""
    if total_revenue >= 50000 and total_events >= 50:
        return "🏆 Master Potter", "You're a pottery legend!"
    elif total_revenue >= 20000 and total_events >= 25:
        return "🎨 Expert Artisan", "Your skills are truly impressive!"
    elif total_revenue >= 5000 and total_events >= 10:
        return "⭐ Skilled Potter", "You're really hitting your stride!"
    elif total_revenue >= 1000 and total_events >= 3:
        return "🌱 Rising Artist", "Your pottery journey is taking off!"
    else:
        return "🔥 Pottery Apprentice", "Every master started here!"

def get_achievement_badges():
    """Check for recent achievements to celebrate"""
    badges = []
    try:
        with closing(get_conn()) as conn:
            recent_events = pd.read_sql_query("""
                SELECT total_revenue, event_date FROM events 
                WHERE status = 'completed' 
                ORDER BY event_date DESC LIMIT 5
            """, conn)
            
            if not recent_events.empty:
                # First $1000 day
                if any(recent_events['total_revenue'] >= 1000):
                    badges.append("💰 First $1K Day!")
                
                # Consistent seller
                if len(recent_events) >= 3 and all(recent_events['total_revenue'] > 0):
                    badges.append("🔥 Consistency Champion!")
            
            # Check sell-through rate
            high_sellthrough = pd.read_sql_query("""
                SELECT AVG(quantity_sold * 1.0 / NULLIF(quantity_brought, 0)) as avg_rate
                FROM event_inventory ei
                JOIN events e ON ei.event_id = e.id
                WHERE e.event_date >= date('now', '-30 days')
            """, conn)
            
            if not high_sellthrough.empty and safe_float(high_sellthrough.iloc[0]['avg_rate']) > 0.8:
                badges.append("🎯 Sell-Through Superstar!")
    
    except Exception as e:
        st.error(f"Error getting badges: {e}")
    
    return badges

# =============== SAFETY HELPERS ===============

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

# =============== DATABASE SETUP ===============

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
        
        # Events
        cur.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
                event_date TEXT NOT NULL, location TEXT, event_type TEXT,
                theme TEXT, theme_description TEXT, color_palette TEXT,
                target_customer TEXT, price_strategy TEXT, booth_fee REAL DEFAULT 0,
                setup_time TEXT, weather TEXT, foot_traffic TEXT,
                total_revenue REAL DEFAULT 0, cash_sales REAL DEFAULT 0,
                card_sales REAL DEFAULT 0, check_sales REAL DEFAULT 0,
                discounts_given REAL DEFAULT 0, rewards_given REAL DEFAULT 0,
                status TEXT DEFAULT 'planned', created_at TEXT, updated_at TEXT
            )
        """)
        
        # Event promotions
        cur.execute("""
            CREATE TABLE IF NOT EXISTS event_promotions (
                id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER NOT NULL,
                promotion_type TEXT NOT NULL, platform TEXT, content TEXT,
                scheduled_date TEXT, target_audience TEXT, engagement_goal TEXT,
                actual_engagement TEXT, leads_generated INTEGER DEFAULT 0,
                sales_attributed REAL DEFAULT 0, created_at TEXT,
                FOREIGN KEY(event_id) REFERENCES events(id)
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
        
        # Goal progress
        cur.execute("""
            CREATE TABLE IF NOT EXISTS goal_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT, goal_id INTEGER NOT NULL,
                progress_date TEXT NOT NULL, value REAL NOT NULL,
                notes TEXT, source TEXT, created_at TEXT,
                FOREIGN KEY(goal_id) REFERENCES business_goals(id)
            )
        """)
        
        # Goal milestones
        cur.execute("""
            CREATE TABLE IF NOT EXISTS goal_milestones (
                id INTEGER PRIMARY KEY AUTOINCREMENT, goal_id INTEGER NOT NULL,
                milestone_name TEXT NOT NULL, target_value REAL NOT NULL,
                achieved_date TEXT, notes TEXT, created_at TEXT,
                FOREIGN KEY(goal_id) REFERENCES business_goals(id)
            )
        """)
        
        conn.commit()

# =============== CORE FUNCTIONS ===============

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

def delete_item(item_id: int):
    try:
        with closing(get_conn()) as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM stock_moves WHERE item_id = ?", (safe_int(item_id),))
            cur.execute("DELETE FROM items WHERE id = ?", (safe_int(item_id),))
            conn.commit()
    except Exception as e:
        st.error(f"Error deleting item: {e}")

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
                INSERT INTO events (name, event_date, location, event_type, theme, theme_description,
                                    color_palette, target_customer, price_strategy, booth_fee, setup_time,
                                    weather, foot_traffic, total_revenue, cash_sales, card_sales, check_sales,
                                    discounts_given, rewards_given, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (safe_string(event_data.get("name")), str(event_data.get("event_date", "")),
                  safe_string(event_data.get("location")), safe_string(event_data.get("event_type")),
                  safe_string(event_data.get("theme")), safe_string(event_data.get("theme_description")),
                  safe_string(event_data.get("color_palette")), safe_string(event_data.get("target_customer")),
                  safe_string(event_data.get("price_strategy")), safe_float(event_data.get("booth_fee")),
                  safe_string(event_data.get("setup_time")), safe_string(event_data.get("weather")),
                  safe_string(event_data.get("foot_traffic")), safe_float(event_data.get("total_revenue")),
                  safe_float(event_data.get("cash_sales")), safe_float(event_data.get("card_sales")),
                  safe_float(event_data.get("check_sales")), safe_float(event_data.get("discounts_given")),
                  safe_float(event_data.get("rewards_given")), safe_string(event_data.get("status", "planned")), now, now))
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

def delete_event(event_id: int):
    try:
        with closing(get_conn()) as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM event_promotions WHERE event_id = ?", (safe_int(event_id),))
            cur.execute("DELETE FROM event_inventory WHERE event_id = ?", (safe_int(event_id),))
            cur.execute("DELETE FROM event_reflections WHERE event_id = ?", (safe_int(event_id),))
            cur.execute("DELETE FROM event_environment WHERE event_id = ?", (safe_int(event_id),))
            cur.execute("DELETE FROM events WHERE id = ?", (safe_int(event_id),))
            conn.commit()
    except Exception as e:
        st.error(f"Error deleting event: {e}")

def get_active_goals():
    try:
        with closing(get_conn()) as conn:
            return pd.read_sql_query("SELECT * FROM business_goals WHERE status = 'active' ORDER BY target_date", conn)
    except Exception as e:
        st.error(f"Error loading goals: {e}")
        return pd.DataFrame()

def create_goal(goal_data):
    try:
        with closing(get_conn()) as conn:
            cur = conn.cursor()
            now = datetime.utcnow().isoformat()
            cur.execute("""
                INSERT INTO business_goals (goal_name, goal_type, target_value, target_date, measurement_unit, category, description, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
            """, (safe_string(goal_data.get("goal_name")), safe_string(goal_data.get("goal_type")),
                  safe_float(goal_data.get("target_value")), str(goal_data.get("target_date", "")),
                  safe_string(goal_data.get("measurement_unit")), safe_string(goal_data.get("category")),
                  safe_string(goal_data.get("description")), now, now))
            goal_id = cur.lastrowid
            conn.commit()
            return goal_id
    except Exception as e:
        st.error(f"Error creating goal: {e}")
        return None

def delete_goal(goal_id: int):
    try:
        with closing(get_conn()) as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM goal_progress WHERE goal_id = ?", (safe_int(goal_id),))
            cur.execute("DELETE FROM goal_milestones WHERE goal_id = ?", (safe_int(goal_id),))
            cur.execute("DELETE FROM business_goals WHERE id = ?", (safe_int(goal_id),))
            conn.commit()
    except Exception as e:
        st.error(f"Error deleting goal: {e}")

def update_goal_progress(goal_id, value, notes="", source="manual"):
    try:
        with closing(get_conn()) as conn:
            cur = conn.cursor()
            now = datetime.utcnow().isoformat()
            today = date.today().isoformat()
            cur.execute("INSERT INTO goal_progress (goal_id, progress_date, value, notes, source, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                       (safe_int(goal_id), today, safe_float(value), safe_string(notes), safe_string(source), now))
            cur.execute("UPDATE business_goals SET current_value = ?, updated_at = ? WHERE id = ?",
                       (safe_float(value), now, safe_int(goal_id)))
            conn.commit()
    except Exception as e:
        st.error(f"Error updating goal progress: {e}")

# =============== ENHANCED UI COMPONENTS ===============

def quick_action_cards():
    """Display fun, actionable quick action cards"""
    st.subheader("🚀 Quick Actions")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("🏺 Add New Piece", help="Create a new pottery item", use_container_width=True):
            st.session_state['nav_to'] = 'New item'
            st.rerun()
    
    with col2:
        if st.button("📅 Plan Event", help="Schedule your next show", use_container_width=True):
            st.session_state['nav_to'] = 'New Event'
            st.rerun()
    
    with col3:
        if st.button("🎯 Smart Planning", help="Get AI recommendations", use_container_width=True):
            st.session_state['nav_to'] = 'Smart Planning'
            st.rerun()
    
    with col4:
        if st.button("📊 Deep Analytics", help="Dive into your data", use_container_width=True):
            st.session_state['nav_to'] = 'Event Analytics'
            st.rerun()

def insights_feed():
    """Display engaging insights in a social media style feed"""
    st.subheader("💡 Your Pottery Insights")
    insights = get_pottery_insights()
    badges = get_achievement_badges()
    
    if badges:
        for badge in badges:
            st.success(f"🏆 **New Achievement Unlocked!** {badge}")
            st.balloons()
    
    for insight in insights:
        if insight['type'] == 'success':
            with st.container():
                st.success(f"**{insight['icon']} {insight['title']}**")
                st.write(insight['message'])
                st.caption(insight['action'])
        elif insight['type'] == 'warning':
            with st.container():
                st.warning(f"**{insight['icon']} {insight['title']}**")
                st.write(insight['message'])
                st.caption(insight['action'])
        else:
            with st.container():
                st.info(f"**{insight['icon']} {insight['title']}**")
                st.write(insight['message'])
                st.caption(insight['action'])

def enhanced_metrics_display():
    """Show metrics in a more engaging, visual way"""
    current_year = date.today().year
    try:
        with closing(get_conn()) as conn:
            yearly_stats = pd.read_sql_query("""
                SELECT COALESCE(SUM(total_revenue), 0) as total_revenue, COUNT(*) as total_events
                FROM events WHERE status = 'completed' AND strftime('%Y', event_date) = ?
            """, conn, params=(str(current_year),))
        
        if not yearly_stats.empty:
            total_revenue = safe_float(yearly_stats.iloc[0]['total_revenue'])
            total_events = safe_int(yearly_stats.iloc[0]['total_events'])
            
            # Only show if there's actual data
            if total_events > 0 or total_revenue > 0:
                level, level_desc = calculate_pottery_level(total_revenue, total_events)
                st.markdown(f"### {level}")
                st.caption(level_desc)
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("💰 This Year's Earnings", f"${total_revenue:,.2f}",
                             delta=f"{pottery_celebration()}" if total_revenue > 0 else None)
                
                with col2:
                    st.metric("🎪 Shows Conquered", total_events,
                             delta="Keep it up!" if total_events > 0 else None)
                
                with col3:
                    avg_per_event = total_revenue / max(total_events, 1)
                    st.metric("⚡ Avg per Show", f"${avg_per_event:.2f}",
                             delta="Strong!" if avg_per_event > 500 else "Growing!")
                
                with col4:
                    st.metric("🚀 Momentum", "🔥 Hot Streak!" if total_events > 0 else "📈 Getting Started!",
                             delta="Keep the energy up!")
            else:
                # New user encouragement
                st.info("📊 **Ready to start tracking?** Complete your first event to see beautiful metrics here!")
    
    except Exception as e:
        st.error(f"Error loading metrics: {str(e)[:50]}...")
        st.info("📊 Metrics will appear here once you complete some events!")

def pottery_item_showcase():
    """Show top items in a visually appealing way"""
    st.subheader("🌟 Your Star Performers")
    
    try:
        with closing(get_conn()) as conn:
            top_items = pd.read_sql_query("""
                SELECT ei.item_name, SUM(ei.quantity_sold) as total_sold,
                       AVG(ei.price_at_event) as avg_price, SUM(ei.quantity_sold * ei.price_at_event) as total_revenue
                FROM event_inventory ei
                JOIN events e ON ei.event_id = e.id
                WHERE e.status = 'completed' AND e.event_date >= date('now', '-90 days')
                GROUP BY ei.item_name ORDER BY total_sold DESC LIMIT 6
            """, conn)
        
        if not top_items.empty:
            cols = st.columns(3)
            for idx, (_, item) in enumerate(top_items.iterrows()):
                with cols[idx % 3]:
                    emoji = pottery_emoji_for_category(item['item_name'])
                    st.metric(f"{emoji} {safe_string(item['item_name'])}", f"{safe_int(item['total_sold'])} sold",
                             delta=f"${safe_float(item['total_revenue']):.0f} earned")
        else:
            st.info("Start selling to see your star performers here! 🌟")
    
    except Exception as e:
        st.error(f"Error loading top items: {e}")

def fun_item_form(existing=None):
    """Enhanced item form with pottery flair"""
    st.subheader("🏺 Add Your Pottery Masterpiece")
    st.write("Every piece tells a story - let's capture yours! ✨")
    
    col1, col2 = st.columns(2)
    
    with col1:
        sku = st.text_input("🏷️ SKU/Code", value=safe_string((existing or {}).get("sku", "")), 
                           placeholder="e.g., MUG001, BOWL-BLU-01").strip()
        name = st.text_input("✨ Piece Name", value=safe_string((existing or {}).get("name", "")),
                            placeholder="e.g., Ocean Breeze Mug, Rustic Dinner Bowl").strip()
        category = st.selectbox("🎨 Category", [
            "Mugs & Cups", "Bowls", "Plates & Dishes", "Vases", "Planters", 
            "Decorative", "Functional", "Sculptures", "Sets", "Other"
        ], index=0 if not existing else 0)
        
        clay_body = st.text_input("🏺 Clay Body", value=safe_string((existing or {}).get("clay_body", "")),
                                 placeholder="e.g., Stoneware, Porcelain, Earthenware")
        glaze = st.text_input("🌈 Glaze", value=safe_string((existing or {}).get("glaze", "")),
                             placeholder="e.g., Celadon, Midnight Blue, Matte White")
    
    with col2:
        size = st.text_input("📏 Size", value=safe_string((existing or {}).get("size", "")),
                            placeholder="e.g., 4\" tall, Large, 12oz")
        price = st.number_input("💰 Price ($)", min_value=0.0, value=safe_float((existing or {}).get("price")), 
                               step=1.0, help="What's this beauty worth?")
        qty_on_hand = st.number_input("📦 Quantity on Hand", min_value=0.0, 
                                     value=safe_float((existing or {}).get("qty_on_hand")), step=1.0)
        location = st.text_input("📍 Location", value=safe_string((existing or {}).get("location", "")),
                                placeholder="e.g., Studio Shelf A, Kiln Room, Display Case")
        image_path = st.text_input("📸 Image URL (optional)", value=safe_string((existing or {}).get("image_path", "")),
                                  placeholder="Link to photo of your piece")
    
    notes = st.text_area("📝 Notes & Story", value=safe_string((existing or {}).get("notes", "")),
                        placeholder="Tell the story of this piece - inspiration, technique, special features...")
    
    if st.button("🚀 Save This Beautiful Piece!", type="primary"):
        if not sku or not name:
            st.error("Don't forget the SKU and name! Every masterpiece needs an identity! 🎯")
            return None
        
        row = {"sku": sku, "name": name, "category": category, "clay_body": clay_body, "glaze": glaze,
               "size": size, "price": price, "qty_on_hand": qty_on_hand, "location": location,
               "notes": notes, "image_path": image_path}
        
        upsert_item(row)
        st.success(f"🎉 {pottery_celebration()} Your piece has been saved!")
        return sku
    
    return None

def fun_event_form():
    """Enhanced event form with personality"""
    st.header("🎪 Plan Your Next Pottery Adventure!")
    st.write("Let's make this event legendary! ✨")
    
    col1, col2 = st.columns(2)
    
    with col1:
        name = st.text_input("🎯 Event Name", placeholder="e.g., Spring Pottery Spectacular!")
        event_date = st.date_input("📅 Show Date")
        location = st.text_input("📍 Location", placeholder="Where the magic happens...")
        event_type = st.selectbox("🎪 Event Type", [
            "Art Fair", "Farmers Market", "Studio Sale", "Gallery Show", 
            "Holiday Market", "Pop-up Shop", "Other"
        ])
    
    with col2:
        booth_fee = st.number_input("💸 Booth Fee", min_value=0.0, step=5.0)
        setup_time = st.text_input("⏰ Setup Time", placeholder="e.g., 7:00 AM")
        weather = st.selectbox("🌤️ Expected Weather", [
            "☀️ Sunny", "⛅ Partly Cloudy", "🌧️ Rainy", "❄️ Snowy", "🌬️ Windy", "🌈 Perfect"
        ])
        foot_traffic = st.selectbox("👥 Expected Crowd", [
            "🔥 Packed House", "😊 Great Turnout", "👌 Steady Flow", "😐 Light Crowd", "🤷 Unknown"
        ])
    
    st.subheader("🎨 Your Creative Vision")
    col3, col4 = st.columns(2)
    
    with col3:
        theme = st.text_input("✨ Collection Theme", placeholder="e.g., Ocean Breeze, Rustic Charm...")
        theme_description = st.text_area("📝 Theme Story", placeholder="Tell the story behind your collection...")
        color_palette = st.text_input("🎨 Color Palette", placeholder="e.g., Blues and whites, Earth tones...")
    
    with col4:
        target_customer = st.selectbox("🎯 Target Audience", [
            "🎁 Holiday gift buyers", "🏠 Home decorators", "🎨 Art collectors",
            "💼 Young professionals", "👨‍👩‍👧‍👦 Families", "🎭 Art enthusiasts",
            "🍽️ Kitchen lovers", "🌱 Garden enthusiasts", "💝 Gift hunters"
        ])
        price_strategy = st.selectbox("💰 Pricing Strategy", [
            "💎 Premium pieces", "📦 Volume sales", "🎯 Mixed range",
            "🎁 Gift-friendly", "🏆 Statement pieces", "🧪 Testing new prices"
        ])
    
    completed = st.checkbox("🎉 Event completed - add results!")
    
    if completed:
        st.subheader("🏆 How Did It Go?")
        st.write("Time to celebrate your achievements! 🎊")
        
        col5, col6 = st.columns(2)
        with col5:
            total_revenue = st.number_input("💰 Total Revenue", min_value=0.0, step=0.01)
            cash_sales = st.number_input("💵 Cash Sales", min_value=0.0, step=0.01)
            card_sales = st.number_input("💳 Card Sales", min_value=0.0, step=0.01)
        
        with col6:
            customer_mood = st.selectbox("😊 Customer Mood", [
                "🥰 Absolutely loved everything!", "😍 Very enthusiastic",
                "😊 Happy and engaged", "🙂 Politely interested", "😐 Just browsing"
            ])
            personal_rating = st.slider("⭐ Your Event Rating", 1, 10, 5, 
                                       help="How do YOU feel about this event?")
    
    if st.button("🚀 Save This Amazing Event!", type="primary"):
        if not name:
            st.error("Don't forget to name your event! 🎯")
            return None
        
        event_data = {
            "name": name, "event_date": event_date, "location": location, "event_type": event_type,
            "theme": theme, "theme_description": theme_description, "color_palette": color_palette,
            "target_customer": target_customer, "price_strategy": price_strategy, "booth_fee": booth_fee,
            "setup_time": setup_time, "weather": weather, "foot_traffic": foot_traffic,
            "total_revenue": total_revenue if completed else 0, "cash_sales": cash_sales if completed else 0,
            "card_sales": card_sales if completed else 0, "check_sales": 0, "discounts_given": 0,
            "rewards_given": 0, "status": "completed" if completed else "planned"
        }
        
        event_id = create_event(event_data)
        if event_id:
            st.success(f"🎉 {pottery_celebration()} Event saved with ID {event_id}")
            if completed and total_revenue > 1000:
                st.balloons()
            return event_id
    
    return None

# =============== MAIN APP ===============

st.set_page_config(page_title="🏺 Pottery Studio Manager", page_icon="🏺", layout="wide")

# Custom CSS for pottery theme
st.markdown("""
<style>
    .stMetric > div[data-testid="metric-container"] {
        background: linear-gradient(135deg, #f5f5dc, #deb887);
        border: 2px solid #d2691e;
        padding: 15px;
        border-radius: 15px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }
    .stButton > button {
        background: linear-gradient(45deg, #8B4513, #CD853F);
        color: white;
        border-radius: 20px;
        border: none;
        padding: 12px 24px;
        font-weight: bold;
        transition: all 0.3s ease;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.2);
    }
    .stSelectbox > div[data-baseweb="select"] > div {
        border-radius: 15px;
        border: 2px solid #d2691e;
    }
    .stTextInput > div > div > input {
        border-radius: 15px;
        border: 2px solid #d2691e;
    }
</style>
""", unsafe_allow_html=True)

# Initialize database
try:
    init_db()
except Exception as e:
    st.error(f"Database initialization error: {e}")
    st.stop()

# Enhanced sidebar
st.sidebar.markdown("# 🏺 Pottery Studio")
st.sidebar.markdown("*Where clay meets data* ✨")

# Demo data option for new users
if st.sidebar.button("🎭 Try Demo Data"):
    if st.sidebar.checkbox("I understand this will add sample data"):
        try:
            add_demo_data()
            st.sidebar.success("🎉 Demo data added! Explore the app!")
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"Error adding demo data: {str(e)[:50]}...")
            st.sidebar.info("No worries! You can still use the app manually.")

menu_options = [
    "🏠 Dashboard", "🎪 Shows & Events", "📊 Analytics", "🎯 Smart Planning",
    "🎖️ Goals & Growth", "📈 Yearly Overview", "🏺 My Pottery", "➕ Add New Piece"
]

menu_mapping = {
    "🏠 Dashboard": "Dashboard", "🎪 Shows & Events": "Shows & Events",
    "📊 Analytics": "Event Analytics", "🎯 Smart Planning": "Smart Planning",
    "🎖️ Goals & Growth": "Business Goals", "📈 Yearly Overview": "Yearly Dashboard",
    "🏺 My Pottery": "Items", "➕ Add New Piece": "New item"
}

# Handle navigation
if 'nav_to' in st.session_state:
    for display_name, internal_name in menu_mapping.items():
        if internal_name == st.session_state['nav_to']:
            selected_menu = display_name
            break
    else:
        selected_menu = "🏠 Dashboard"
    del st.session_state['nav_to']
else:
    selected_menu = st.sidebar.selectbox("Navigate to:", menu_options)

menu = menu_mapping.get(selected_menu, "Dashboard")

# ENHANCED DASHBOARD
if menu == "Dashboard":
    st.title("🏺 Your Pottery Studio Command Center")
    st.markdown("*Welcome back, clay artist! Here's what's happening in your pottery world* ✨")
    
    quick_action_cards()
    # Milestone tracking
    milestone = get_next_milestone()
    if milestone:
        st.subheader("🎯 Your Next Milestone")
        progress = min((total_revenue / milestone["target"]) * 100, 100)
        st.progress(progress / 100)
        remaining = milestone["target"] - total_revenue
        if remaining > 0:
            st.write(f"**{milestone['milestone']}:** ${remaining:,.2f} to go!")
            st.caption(milestone["message"])
        else:
            st.success(f"🏆 **{milestone['milestone']} ACHIEVED!** {milestone['message']}")
    
    # Pottery streak
    streak = calculate_pottery_streak()
    if streak > 0:
        st.success(f"🔥 **Hot Streak!** {streak} consecutive successful events!")
    
    st.divider()
    
    # Pottery wisdom
    wisdom = get_pottery_wisdom()
    if "quote" in wisdom:
        st.markdown(f"*\"{wisdom['quote']}\"*")
        st.caption(f"— {wisdom['author']}")
    else:
        st.info(wisdom["tip"])
    
    st.divider()
    enhanced_metrics_display()
    st.divider()
    insights_feed()
    st.divider()
    pottery_item_showcase()
    
    pottery_quotes = [
        "🏺 *'In pottery, as in life, patience and pressure create beauty.'*",
        "✨ *'Every piece tells a story, every sale writes a new chapter.'*",
        "🎨 *'Clay doesn't lie. Your passion shows in every curve.'*",
        "🔥 *'From earth to art, from studio to success!'*"
    ]
    st.markdown(f"---\n{random.choice(pottery_quotes)}")

elif menu == "New item":
    st.title("🏺 Add a New Pottery Piece")
    st.markdown("*Bring your latest creation into the digital world!* ✨")
    saved = fun_item_form()
    if saved:
        st.session_state["open_item"] = fetch_item_by_sku(saved)
        st.rerun()

elif menu == "Items":
    st.title("🏺 Your Pottery Collection")
    st.markdown("*Every piece in your creative arsenal* 🎨")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        q = st.text_input("🔍 Search your collection", placeholder="Search by name, SKU, category, glaze...")
    with col2:
        if st.button("➕ Add New Piece", type="primary"):
            st.session_state['nav_to'] = 'New item'
            st.rerun()
    
    df = fetch_items_df(q)
    if not df.empty:
        # Enhanced display with emojis
        display_df = df.copy()
        display_df['Category'] = display_df['category'].apply(lambda x: f"{pottery_emoji_for_category(x)} {x}" if x else "🏺 General")
        st.dataframe(display_df[['sku', 'name', 'Category', 'price', 'qty_on_hand', 'glaze']], use_container_width=True)
        
        st.divider()
        sku_pick = st.text_input("🎯 Open item by SKU")
        if st.button("Open Item") and sku_pick:
            item = fetch_item_by_sku(sku_pick)
            if not item:
                st.error("Item not found! 🔍")
            else:
                st.session_state["open_item"] = item
        
        if "open_item" in st.session_state:
            item = st.session_state["open_item"]
            st.subheader(f"🏺 {safe_string(item['name'])}")
            
            col1, col2 = st.columns([1, 2])
            with col1:
                if item.get("image_path"):
                    try:
                        st.image(safe_string(item["image_path"]), caption=safe_string(item["name"]), use_column_width=True)
                    except:
                        st.write("📸 Image not available")
                else:
                    emoji = pottery_emoji_for_category(item.get('category', ''))
                    st.markdown(f"<div style='text-align: center; font-size: 100px;'>{emoji}</div>", unsafe_allow_html=True)
            
            with col2:
                st.write(f"**SKU:** {safe_string(item.get('sku', ''))}")
                st.write(f"**Category:** {pottery_emoji_for_category(item.get('category', ''))} {safe_string(item.get('category', ''))}")
                st.write(f"**Clay Body:** {safe_string(item.get('clay_body', ''))}")
                st.write(f"**Glaze:** {safe_string(item.get('glaze', ''))}")
                st.write(f"**Size:** {safe_string(item.get('size', ''))}")
                st.write(f"**Price:** ${safe_float(item.get('price', 0)):.2f}")
                st.write(f"**In Stock:** {safe_int(item.get('qty_on_hand', 0))}")
                st.write(f"**Location:** {safe_string(item.get('location', ''))}")
                if item.get('notes'):
                    st.write(f"**Notes:** {safe_string(item.get('notes', ''))}")
            
            # Stock adjustment
            st.subheader("📦 Adjust Stock")
            col3, col4 = st.columns(2)
            with col3:
                qty = st.number_input("Quantity change", value=0.0, step=1.0)
            with col4:
                ref = st.text_input("Reference or reason")
            
            if st.button("📝 Record Movement"):
                if qty == 0:
                    st.warning("Quantity change cannot be zero! 🚫")
                else:
                    record_move(safe_int(item["id"]), "adjustment", qty, ref)
                    st.success(f"🎉 Movement recorded! {pottery_celebration()}")
                    # Refresh item data
                    st.session_state["open_item"] = fetch_item_by_sku(item["sku"])
                    st.rerun()
            
            # Edit/Delete buttons
            col5, col6 = st.columns(2)
            with col5:
                if st.button("✏️ Edit Item"):
                    st.session_state["edit_sku"] = safe_string(item["sku"])
            with col6:
                if st.button("🗑️ Delete Item", type="secondary"):
                    delete_item(safe_int(item["id"]))
                    st.success("🗑️ Item deleted!")
                    st.session_state.pop("open_item", None)
                    st.rerun()
    
    else:
        st.info("No items found. Start creating your pottery collection! 🏺")
    
    # Edit form
    if "edit_sku" in st.session_state:
        existing = fetch_item_by_sku(st.session_state["edit_sku"])
        st.subheader("✏️ Edit Item")
        saved = fun_item_form(existing)
        if saved:
            st.session_state.pop("edit_sku", None)
            st.session_state["open_item"] = fetch_item_by_sku(saved)
            st.rerun()

elif menu == "Shows & Events":
    st.title("🎪 Your Pottery Show Adventure!")
    st.markdown("*Every event is a new opportunity to share your art* 🌟")
    
    if st.button("🎯 Plan a New Event", type="primary"):
        with st.expander("✨ Create New Event", expanded=True):
            fun_event_form()
    
    events_df = get_events()
    if not events_df.empty:
        st.subheader("📅 Your Event Timeline")
        # Enhance events display
        display_events = events_df.copy()
        display_events['Status'] = display_events['status'].apply(
            lambda x: "✅ Completed" if x == 'completed' else "📅 Planned"
        )
        st.dataframe(display_events[['name', 'event_date', 'location', 'event_type', 'Status', 'total_revenue']], 
                    use_container_width=True)
        
        # Event management
        names = [f"{safe_string(r['name'])} - {safe_string(r['event_date'])}" for _, r in events_df.iterrows()]
        pick = st.selectbox("🎯 Select an event to manage", names)
        
        if pick:
            event_id = safe_int(events_df.iloc[names.index(pick)]['id'])
            event = get_event_by_id(event_id)
            
            if event:
                event_name = safe_string(event.get('name', 'Unknown Event'))
                st.subheader(f"🎪 Managing: {event_name}")
                
                # Delete option
                col1, col2 = st.columns([3, 1])
                with col2:
                    confirm = st.checkbox("Confirm delete", key=f"confirm_del_evt_{safe_int(event['id'])}")
                    if st.button("🗑️ Delete Event", key=f"del_evt_{safe_int(event['id'])}"):
                        if confirm:
                            delete_event(safe_int(event['id']))
                            st.success("🗑️ Event deleted!")
                            st.rerun()
                        else:
                            st.warning("Check confirm delete first! ⚠️")
                
                # Event details
                if event.get('status') == 'completed':
                    st.success(f"✅ Completed Event - Revenue: ${safe_float(event['total_revenue']):.2f}")
                else:
                    st.info("📅 Planned Event")
                
                st.write(f"**📍 Location:** {safe_string(event.get('location', ''))}")
                st.write(f"**🎪 Type:** {safe_string(event.get('event_type', ''))}")
                if event.get('theme'):
                    st.write(f"**🎨 Theme:** {safe_string(event.get('theme', ''))}")
                if event.get('target_customer'):
                    st.write(f"**🎯 Target:** {safe_string(event.get('target_customer', ''))}")
    
    else:
        st.info("No events yet. Plan your first pottery adventure! 🎪")

elif menu == "Business Goals":
    st.title("🎖️ Your Pottery Goals & Growth")
    st.markdown("*Dream big, track progress, celebrate wins!* 🌟")
    
    goals = get_active_goals()
    if not goals.empty:
        st.subheader("🏆 Goal Progress Overview")
        for _, goal in goals.iterrows():
            progress = (safe_float(goal['current_value']) / safe_float(goal['target_value'])) * 100 if safe_float(goal['target_value']) else 0
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.write(f"**🎯 {safe_string(goal['goal_name'])}**")
                st.caption(f"{safe_string(goal['category'])}")
            with col2:
                st.metric("Progress", f"{safe_float(goal['current_value']):.0f} / {safe_float(goal['target_value']):.0f} {safe_string(goal['measurement_unit'])}")
            with col3:
                st.progress(min(progress/100, 1.0))
                st.write(f"{progress:.1f}%")
            with col4:
                try:
                    target_date = datetime.strptime(safe_string(goal['target_date']), '%Y-%m-%d').date()
                    days_remaining = (target_date - date.today()).days
                    if days_remaining >= 0:
                        st.write(f"⏰ {days_remaining} days left")
                    else:
                        st.write(f"⚠️ {abs(days_remaining)} days overdue")
                except:
                    st.write("")
        
        st.divider()
    
    # Create new goal
    with st.expander("🎯 Create New Goal", expanded=len(goals)==0):
        col1, col2 = st.columns(2)
        with col1:
            goal_name = st.text_input("🎯 Goal Name")
            goal_type = st.selectbox("📊 Goal Type", ["revenue", "events", "social_media", "custom"])
            target_value = st.number_input("🎯 Target Value", min_value=0.0, step=1.0)
        with col2:
            target_date = st.date_input("📅 Target Date", value=date(date.today().year, 12, 31))
            category = st.selectbox("📂 Category", ["Annual Goals", "Quarterly Goals", "Monthly Goals", "Growth Targets", "Other"])
            unit_default = {"revenue":"$", "events":"events", "social_media":"followers"}.get(goal_type, "units")
            measurement_unit = st.text_input("📏 Unit", value=unit_default)
        
        description = st.text_area("📝 Description")
        
        if st.button("🚀 Create Goal", type="primary"):
            if goal_name and target_value > 0:
                gid = create_goal({
                    "goal_name": goal_name, "goal_type": goal_type, "target_value": target_value,
                    "target_date": target_date, "measurement_unit": measurement_unit,
                    "category": category, "description": description
                })
                if gid:
                    st.success(f"🎉 {pottery_celebration()} Goal created!")
                    st.rerun()
            else:
                st.error("Please fill goal name and target value! 📝")
    
    # Update progress
    if not goals.empty:
        st.subheader("📈 Update Goal Progress")
        options = [f"{safe_string(r['goal_name'])} (Current {safe_float(r['current_value']):.0f})" for _, r in goals.iterrows()]
        idx = st.selectbox("Select Goal", range(len(options)), format_func=lambda i: options[i])
        sel = goals.iloc[idx]
        
        col1, col2 = st.columns(2)
        with col1:
            new_val = st.number_input("New Value", min_value=0.0, value=safe_float(sel['current_value']), step=1.0)
        with col2:
            notes = st.text_input("Notes")
        
        col3, col4 = st.columns(2)
        with col3:
            if st.button("📈 Update Progress"):
                update_goal_progress(safe_int(sel['id']), new_val, notes)
                st.success("📈 Progress updated!")
                st.rerun()
        with col4:
            del_confirm = st.checkbox("Confirm delete")
            if st.button("🗑️ Delete Goal"):
                if del_confirm:
                    delete_goal(safe_int(sel['id']))
                    st.success("🗑️ Goal deleted!")
                    st.rerun()
                else:
                    st.warning("Check confirm delete first! ⚠️")

elif menu == "Event Analytics":
    st.title("📊 Your Pottery Analytics Hub")
    st.markdown("*Data-driven insights for the modern potter* 📈")
    
    try:
        with closing(get_conn()) as conn:
            # Revenue by event type
            revenue_by_type = pd.read_sql_query("""
                SELECT event_type, AVG(total_revenue) as avg_revenue, COUNT(*) as event_count, SUM(total_revenue) as total_revenue
                FROM events WHERE status = 'completed' GROUP BY event_type
            """, conn)
            
            # Top selling items
            top_items = pd.read_sql_query("""
                SELECT ei.item_name, SUM(ei.quantity_sold) as total_sold, AVG(ei.price_at_event) as avg_price,
                       SUM(ei.quantity_sold * ei.price_at_event) as total_revenue,
                       AVG(ei.quantity_sold * 1.0 / NULLIF(ei.quantity_brought, 0)) as avg_sell_through_rate
                FROM event_inventory ei
                WHERE ei.quantity_sold > 0
                GROUP BY ei.item_name
                ORDER BY total_sold DESC
                LIMIT 10
            """, conn)
            
            # Monthly trends
            monthly_trends = pd.read_sql_query("""
                SELECT strftime('%Y-%m', event_date) as month, SUM(total_revenue) as revenue, COUNT(*) as events
                FROM events WHERE status = 'completed'
                GROUP BY strftime('%Y-%m', event_date)
                ORDER BY month
            """, conn)
            
            # Price analysis
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
    
        # Display analytics
        if not revenue_by_type.empty:
            st.subheader("🎪 Performance by Event Type")
            col1, col2 = st.columns(2)
            
            with col1:
                st.bar_chart(revenue_by_type.set_index('event_type')['avg_revenue'])
                st.caption("Average Revenue per Event Type")
            
            with col2:
                # Create a nice table with emojis
                display_revenue = revenue_by_type.copy()
                display_revenue['emoji'] = display_revenue['event_type'].apply(lambda x: 
                    "🎨" if "Art" in str(x) else "🚜" if "Farmers" in str(x) else 
                    "🏠" if "Studio" in str(x) else "🖼️" if "Gallery" in str(x) else 
                    "🎄" if "Holiday" in str(x) else "🎪")
                display_revenue['Event Type'] = display_revenue['emoji'] + " " + display_revenue['event_type']
                st.dataframe(display_revenue[['Event Type', 'avg_revenue', 'event_count', 'total_revenue']])
        
        if not top_items.empty:
            st.subheader("🌟 Your Bestsellers Hall of Fame")
            
            # Make it more engaging
            col1, col2, col3 = st.columns(3)
            
            # Top 3 with special recognition
            for idx, (_, item) in enumerate(top_items.head(3).iterrows()):
                with [col1, col2, col3][idx]:
                    emoji = pottery_emoji_for_category(item['item_name'])
                    medal = ["🥇", "🥈", "🥉"][idx]
                    st.metric(
                        f"{medal} {emoji} {safe_string(item['item_name'])}",
                        f"{safe_int(item['total_sold'])} sold",
                        delta=f"${safe_float(item['total_revenue']):.0f} earned"
                    )
            
            # Full table
            st.dataframe(top_items, use_container_width=True)
        
        if not price_analysis.empty:
            st.subheader("💰 Sweet Spot Pricing Analysis")
            col1, col2 = st.columns(2)
            
            with col1:
                st.bar_chart(price_analysis.set_index('price_range')['avg_sell_through_rate'])
                st.caption("Sell-Through Rate by Price Range")
            
            with col2:
                # Find the best performing price range
                best_range = price_analysis.loc[price_analysis['avg_sell_through_rate'].idxmax()]
                st.success(f"🎯 **Sweet Spot:** {best_range['price_range']} range has the highest sell-through rate at {best_range['avg_sell_through_rate']:.1%}!")
                st.info(f"💡 **Insight:** Consider pricing more pieces in the {best_range['price_range']} range for better sales velocity!")
        
        if not monthly_trends.empty:
            st.subheader("📈 Your Revenue Journey")
            st.line_chart(monthly_trends.set_index('month')['revenue'])
            
            # Add trend insights
            if len(monthly_trends) >= 2:
                recent_revenue = safe_float(monthly_trends.iloc[-1]['revenue'])
                previous_revenue = safe_float(monthly_trends.iloc[-2]['revenue'])
                
                if recent_revenue > previous_revenue:
                    growth = ((recent_revenue - previous_revenue) / previous_revenue) * 100
                    st.success(f"📈 You're trending UP! {growth:.1f}% growth from last period!")
                elif recent_revenue < previous_revenue:
                    decline = ((previous_revenue - recent_revenue) / previous_revenue) * 100
                    st.info(f"📊 Revenue dipped {decline:.1f}% - normal fluctuations! Keep creating!")
                else:
                    st.info("📊 Steady as she goes! Consistent performance!")
    
    except Exception as e:
        st.error(f"Error loading analytics: {e}")
        st.info("Start adding events and sales data to see beautiful analytics here! 📊")

elif menu == "Smart Planning":
    st.title("🎯 Smart Event Planning Assistant")
    st.markdown("*AI-powered recommendations for pottery success* 🤖✨")
    
    # Event planning form
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📋 Tell us about your upcoming event")
        event_type = st.selectbox("🎪 Event Type", [
            "Art Fair", "Farmers Market", "Studio Sale", "Gallery Show", 
            "Holiday Market", "Pop-up Shop", "Other"
        ])
        season = st.selectbox("🌍 Season", ["Winter", "Spring", "Summer", "Fall"])
        
    with col2:
        st.subheader("🎯 Your Goals")
        target_revenue = st.number_input("💰 Revenue Goal", min_value=0.0, step=100.0, value=1000.0)
        booth_fee = st.number_input("💸 Booth Fee", min_value=0.0, step=25.0)
        
    event_size = st.selectbox("👥 Expected Event Size", [
        "🏠 Intimate (< 50 people)", "👥 Medium (50-200 people)", 
        "🎪 Large (200-500 people)", "🎆 Festival (500+ people)"
    ])
    
    if st.button("🚀 Generate Smart Recommendations", type="primary"):
        st.subheader("🎯 Your Personalized Recommendations")
        
        try:
            with closing(get_conn()) as conn:
                # Get smart inventory recommendations
                where_conditions = ["e.status = 'completed'", "ei.quantity_brought > 0"]
                params = []
                
                if event_type != "Other":
                    where_conditions.append("e.event_type = ?")
                    params.append(event_type)
                
                # Season mapping
                season_months = {
                    'Winter': '(12,1,2)', 'Spring': '(3,4,5)', 
                    'Summer': '(6,7,8)', 'Fall': '(9,10,11)'
                }
                where_conditions.append(f"CAST(strftime('%m', e.event_date) AS INTEGER) IN {season_months[season]}")
                
                where_clause = " AND ".join(where_conditions)
                
                recommendations = pd.read_sql_query(f"""
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
                """, conn, params=params)
        
            if not recommendations.empty:
                st.success("🎊 Great news! I found some winning recommendations based on your past events!")
                
                # Smart recommendations with personality
                st.subheader("🏺 Recommended Inventory Mix")
                
                total_expected_revenue = 0
                for idx, (_, item) in enumerate(recommendations.head(8).iterrows()):
                    emoji = pottery_emoji_for_category(item['item_name'])
                    expected_sales = safe_float(item['avg_sold'])
                    optimal_price = safe_float(item['optimal_price'])
                    expected_revenue = expected_sales * optimal_price
                    total_expected_revenue += expected_revenue
                    
                    col1, col2, col3, col4, col5 = st.columns(5)
                    
                    with col1:
                        st.write(f"**{emoji} {safe_string(item['item_name'])}**")
                    with col2:
                        st.metric("Bring", f"{safe_float(item['avg_brought']):.0f}")
                    with col3:
                        st.metric("Expected Sales", f"{expected_sales:.0f}")
                    with col4:
                        st.metric("Price", f"${optimal_price:.2f}")
                    with col5:
                        st.metric("Revenue", f"${expected_revenue:.2f}")
                
                # Performance summary
                st.subheader("📊 Projected Performance")
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("💰 Expected Revenue", f"${total_expected_revenue:.2f}")
                with col2:
                    st.metric("🎯 Revenue Goal", f"${target_revenue:.2f}")
                with col3:
                    difference = total_expected_revenue - target_revenue
                    st.metric("📈 Difference", f"${difference:.2f}", 
                             delta="Above goal! 🎉" if difference > 0 else "Below goal 📋")
                with col4:
                    profit = total_expected_revenue - booth_fee
                    st.metric("💎 Expected Profit", f"${profit:.2f}")
                
                # Stock check
                current_inventory = fetch_items_df()
                if not current_inventory.empty:
                    st.subheader("📦 Stock Reality Check")
                    
                    stock_alerts = []
                    for _, item in recommendations.head(5).iterrows():
                        item_name = safe_string(item['item_name'])
                        needed = safe_float(item['avg_brought'])
                        
                        # Try to find matching items in inventory
                        matches = current_inventory[current_inventory['name'].str.contains(item_name, case=False, na=False)]
                        
                        if not matches.empty:
                            available = safe_float(matches.iloc[0]['qty_on_hand'])
                            
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.write(f"**{pottery_emoji_for_category(item_name)} {item_name}**")
                            with col2:
                                st.write(f"Need: {needed:.0f}")
                            with col3:
                                st.write(f"Have: {available:.0f}")
                            with col4:
                                if available >= needed:
                                    st.success("✅ Ready to go!")
                                elif available >= needed * 0.8:
                                    st.warning("⚠️ Close call")
                                else:
                                    st.error("🚨 Need more!")
                                    stock_alerts.append(item_name)
                    
                    if stock_alerts:
                        st.info(f"🎯 **Action Items:** Consider making more of these popular pieces: {', '.join(stock_alerts)}")
                
                # Seasonal tips
                seasonal_tips = {
                    'Winter': {
                        'emoji': '❄️',
                        'tip': 'Focus on warm, cozy pieces like mugs and candle holders. Holiday themes sell well!',
                        'colors': 'Deep blues, whites, metallics'
                    },
                    'Spring': {
                        'emoji': '🌸',
                        'tip': 'Garden planters and fresh, bright pieces are popular. Think renewal and growth!',
                        'colors': 'Pastels, greens, fresh blues'
                    },
                    'Summer': {
                        'emoji': '☀️',
                        'tip': 'Outdoor entertaining pieces and bright colors. Serving dishes and planters shine!',
                        'colors': 'Vibrant blues, sunny yellows, coral'
                    },
                    'Fall': {
                        'emoji': '🍂',
                        'tip': 'Cozy home pieces and earth tones. Soup bowls and decorative items are favorites!',
                        'colors': 'Earth tones, deep oranges, warm browns'
                    }
                }
                
                tip = seasonal_tips[season]
                st.subheader(f"{tip['emoji']} {season} Success Tips")
                st.info(f"**🎨 {season} Strategy:** {tip['tip']}")
                st.info(f"**🌈 Hot Colors:** {tip['colors']}")
                
                # Event-specific tips
                event_tips = {
                    'Art Fair': '🎨 Focus on unique, artistic pieces. Customers expect creativity and craftsmanship.',
                    'Farmers Market': '🚜 Functional pieces work best. Think kitchen items and planters.',
                    'Studio Sale': '🏠 Great for clearing inventory and offering deals on seconds.',
                    'Gallery Show': '🖼️ Showcase your finest work. Quality over quantity.',
                    'Holiday Market': '🎄 Gift sets and holiday themes. Price for gift-giving.',
                    'Pop-up Shop': '⚡ Eye-catching displays and Instagram-worthy pieces.'
                }
                
                if event_type in event_tips:
                    st.info(f"**🎪 {event_type} Pro Tip:** {event_tips[event_type]}")
            
            else:
                st.info("🌱 **Starting Fresh?** No historical data yet, but here are some general recommendations!")
                
                # Default recommendations for new potters
                st.subheader("🏺 Beginner's Success Kit")
                
                beginner_items = [
                    {'name': 'Coffee Mugs', 'emoji': '☕', 'bring': '12-15', 'price': '$18-25', 'why': 'Everyone drinks coffee!'},
                    {'name': 'Small Bowls', 'emoji': '🥣', 'bring': '8-10', 'price': '$15-22', 'why': 'Versatile and popular'},
                    {'name': 'Planters', 'emoji': '🪴', 'bring': '6-8', 'price': '$25-35', 'why': 'Great profit margins'},
                    {'name': 'Decorative Pieces', 'emoji': '🎨', 'bring': '4-6', 'price': '$30-50', 'why': 'Show your artistry'},
                ]
                
                for item in beginner_items:
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.write(f"**{item['emoji']} {item['name']}**")
                    with col2:
                        st.write(f"Bring: {item['bring']}")
                    with col3:
                        st.write(f"Price: {item['price']}")
                    with col4:
                        st.write(f"*{item['why']}*")
                
                st.success("🎯 **Estimated Revenue:** $800-1,200 for this starter mix!")
        
        except Exception as e:
            st.error(f"Error generating recommendations: {e}")
            st.info("Add some completed events to get personalized recommendations! 📊")

elif menu == "Yearly Dashboard":
    st.title("📈 Your Annual Pottery Journey")
    st.markdown("*Celebrating a year of clay, creativity, and commerce* 🏆")
    
    current_year = date.today().year
    selected_year = st.selectbox("📅 Select Year", [current_year, current_year-1, current_year-2], index=0)
    
    try:
        with closing(get_conn()) as conn:
            # Yearly revenue
            yearly_revenue = pd.read_sql_query("""
                SELECT SUM(total_revenue) as total_revenue, COUNT(*) as total_events
                FROM events 
                WHERE status = 'completed' AND strftime('%Y', event_date) = ?
            """, conn, params=(str(selected_year),))
            
            # Monthly breakdown
            monthly_breakdown = pd.read_sql_query("""
                SELECT strftime('%m', event_date) as month, SUM(total_revenue) as revenue, COUNT(*) as events
                FROM events 
                WHERE status = 'completed' AND strftime('%Y', event_date) = ?
                GROUP BY strftime('%m', event_date)
                ORDER BY month
            """, conn, params=(str(selected_year),))
            
            # Previous year for comparison
            prev_year_revenue = pd.read_sql_query("""
                SELECT SUM(total_revenue) as total_revenue, COUNT(*) as total_events
                FROM events 
                WHERE status = 'completed' AND strftime('%Y', event_date) = ?
            """, conn, params=(str(selected_year - 1),))
    
        if not yearly_revenue.empty and yearly_revenue.iloc[0]['total_revenue']:
            total_rev = safe_float(yearly_revenue.iloc[0]['total_revenue'])
            total_events = safe_int(yearly_revenue.iloc[0]['total_events'])
            avg_per_event = total_rev / max(total_events, 1)
            
            # Previous year comparison
            prev_rev = safe_float(prev_year_revenue.iloc[0]['total_revenue']) if not prev_year_revenue.empty else 0
            prev_events = safe_int(prev_year_revenue.iloc[0]['total_events']) if not prev_year_revenue.empty else 0
            
            # Calculate growth
            rev_growth = ((total_rev - prev_rev) / prev_rev * 100) if prev_rev else None
            evt_growth = ((total_events - prev_events) / prev_events * 100) if prev_events else None
            
            # Year overview metrics
            st.subheader(f"🏆 {selected_year} at a Glance")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                growth_delta = f"{rev_growth:+.1f}%" if rev_growth is not None else None
                st.metric("💰 Total Revenue", f"${total_rev:,.2f}", delta=growth_delta)
            
            with col2:
                event_delta = f"{evt_growth:+.1f}%" if evt_growth is not None else None
                st.metric("🎪 Total Events", total_events, delta=event_delta)
            
            with col3:
                st.metric("⚡ Average per Event", f"${avg_per_event:,.2f}")
            
            with col4:
                # Check goals
                goals = get_active_goals()
                if not goals.empty:
                    year_goals = goals[goals['target_date'].str.startswith(str(selected_year))]
                    if not year_goals.empty:
                        revenue_goals = year_goals[year_goals['goal_type'] == 'revenue']
                        if not revenue_goals.empty:
                            goal_value = safe_float(revenue_goals.iloc[0]['target_value'])
                            progress = (total_rev / goal_value) * 100 if goal_value else 0
                            st.metric("🎯 Goal Progress", f"{progress:.1f}%")
                        else:
                            st.metric("🎯 Year Status", "Strong!" if total_rev > 5000 else "Growing!")
                    else:
                        st.metric("🎯 Year Status", "Strong!" if total_rev > 5000 else "Growing!")
                else:
                    st.metric("🎯 Year Status", "Strong!" if total_rev > 5000 else "Growing!")
            
            # Achievement celebration
            if total_rev > 10000:
                st.success("🏆 **AMAZING!** You've hit 5-figure revenue! That's master potter territory!")
                st.balloons()
            elif total_rev > 5000:
                st.success("🌟 **FANTASTIC!** You're well on your way to pottery success!")
            elif total_rev > 1000:
                st.success("🚀 **GREAT START!** Your pottery journey is taking off!")
            
            # Monthly visualization
            if not monthly_breakdown.empty:
                st.subheader(f"📊 {selected_year} Month-by-Month Journey")
                
                # Add month names
                month_names = {
                    '01': 'Jan', '02': 'Feb', '03': 'Mar', '04': 'Apr',
                    '05': 'May', '06': 'Jun', '07': 'Jul', '08': 'Aug',
                    '09': 'Sep', '10': 'Oct', '11': 'Nov', '12': 'Dec'
                }
                monthly_breakdown['month_name'] = monthly_breakdown['month'].map(month_names)
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("📈 Revenue Trend")
                    st.line_chart(monthly_breakdown.set_index('month_name')['revenue'])
                
                with col2:
                    st.subheader("📊 Monthly Breakdown")
                    st.bar_chart(monthly_breakdown.set_index('month_name')['revenue'])
                
                # Best and worst months
                best_month = monthly_breakdown.loc[monthly_breakdown['revenue'].idxmax()]
                worst_month = monthly_breakdown.loc[monthly_breakdown['revenue'].idxmin()]
                
                col3, col4 = st.columns(2)
                with col3:
                    st.success(f"🏆 **Best Month:** {best_month['month_name']} with ${safe_float(best_month['revenue']):,.2f}!")
                
                with col4:
                    st.info(f"📈 **Growth Opportunity:** {worst_month['month_name']} - plan more events!")
                
                # Full monthly table
                st.subheader("📋 Complete Monthly Summary")
                display_monthly = monthly_breakdown[['month_name', 'revenue', 'events']].copy()
                display_monthly.columns = ['Month', 'Revenue', 'Events']
                display_monthly['Revenue'] = display_monthly['Revenue'].apply(lambda x: f"${x:,.2f}")
                st.dataframe(display_monthly, use_container_width=True)
        
        else:
            st.info(f"📅 No completed events found for {selected_year}. Start planning your pottery adventures!")
            
            # Motivational content for new users
            st.subheader("🚀 Ready to Start Your {selected_year} Journey?")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🎯 Set Your First Goal", type="primary"):
                    st.session_state['nav_to'] = 'Business Goals'
                    st.rerun()
            
            with col2:
                if st.button("📅 Plan Your First Event", type="primary"):
                    st.session_state['nav_to'] = 'New Event'
                    st.rerun()
    
    except Exception as e:
        st.error(f"Error loading yearly data: {e}")

else:
    # Placeholder for any remaining menu items
    st.title(f"🚧 {selected_menu} - Coming Soon!")
    st.markdown("*This feature is being crafted with love!* ✨")
    st.info("Check back soon for more pottery goodness! 🏺")

# Enhanced footer
st.sidebar.markdown("---")

# Quick stats in sidebar
try:
    with closing(get_conn()) as conn:
        quick_stats = pd.read_sql_query("""
            SELECT 
                COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_events,
                COUNT(CASE WHEN status = 'planned' THEN 1 END) as planned_events,
                SUM(CASE WHEN status = 'completed' THEN total_revenue ELSE 0 END) as total_revenue
            FROM events
        """, conn)
        
        item_stats = pd.read_sql_query("SELECT COUNT(*) as total_items FROM items", conn)
        
        if not quick_stats.empty:
            completed = safe_int(quick_stats.iloc[0]['completed_events'])
            planned = safe_int(quick_stats.iloc[0]['planned_events'])
            revenue = safe_float(quick_stats.iloc[0]['total_revenue'])
            items = safe_int(item_stats.iloc[0]['total_items']) if not item_stats.empty else 0
            
            st.sidebar.markdown("### 📊 Quick Stats")
            st.sidebar.metric("🏺 Pottery Pieces", items)
            st.sidebar.metric("✅ Events Done", completed)
            st.sidebar.metric("📅 Events Planned", planned)
            st.sidebar.metric("💰 Total Revenue", f"${revenue:,.0f}")
            
            # Motivational message based on progress
            if revenue >= 10000:
                st.sidebar.success("🏆 Master Potter!")
            elif revenue >= 5000:
                st.sidebar.success("⭐ Skilled Artist!")
            elif revenue >= 1000:
                st.sidebar.info("🌱 Rising Potter!")
            elif completed > 0:
                st.sidebar.info("🔥 Getting Started!")
            else:
                st.sidebar.info("🚀 Ready to Begin!")

except Exception as e:
    pass  # Fail silently for sidebar stats

st.sidebar.markdown("### 💪 Keep Creating!")
st.sidebar.markdown("*Every piece is progress* 🎨")

# Random motivation
motivations = [
    "🎯 Your next masterpiece awaits!",
    "🔥 Clay + passion = magic!",
    "✨ Create something beautiful today!",
    "🏺 Every potter started with clay!",
    "🌟 Your art makes the world brighter!"
]
st.sidebar.markdown(f"*{random.choice(motivations)}*")

# Add some pottery wisdom at the bottom
pottery_tips = [
    "💡 Tip: Take photos of your best pieces for social media!",
    "🎯 Pro Tip: Track which glazes sell best at different events!",
    "🌟 Remember: Every potter was once a beginner!",
    "🔥 Inspiration: Your next masterpiece is one throw away!"
]
st.sidebar.markdown(f"*{random.choice(pottery_tips)}*")
