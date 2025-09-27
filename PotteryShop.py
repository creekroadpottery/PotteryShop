import streamlit as st
import pandas as pd
import sqlite3
from contextlib import closing
from datetime import datetime, date
import numpy as np

DB_PATH = "pottery_shop.db"

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
        
        # Core tables (keeping the same structure)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sku TEXT UNIQUE, name TEXT NOT NULL, category TEXT,
                clay_body TEXT, glaze TEXT, size TEXT, price REAL DEFAULT 0,
                qty_on_hand REAL DEFAULT 0, location TEXT, notes TEXT,
                image_path TEXT, created_at TEXT, updated_at TEXT
            )
        """)
        
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
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS event_inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER NOT NULL,
                item_sku TEXT NOT NULL, item_name TEXT NOT NULL,
                quantity_brought INTEGER DEFAULT 0, quantity_sold INTEGER DEFAULT 0,
                price_at_event REAL DEFAULT 0, UNIQUE(event_id, item_sku),
                FOREIGN KEY(event_id) REFERENCES events(id)
            )
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS event_reflections (
                id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER NOT NULL,
                category TEXT NOT NULL, content TEXT NOT NULL,
                customer_interaction INTEGER DEFAULT 0, price_point_insight INTEGER DEFAULT 0,
                created_at TEXT, FOREIGN KEY(event_id) REFERENCES events(id)
            )
        """)
        
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

def get_business_insights():
    """Generate thoughtful business insights based on actual data"""
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
                    AVG(quantity_sold * 1.0 / NULLIF(quantity_brought, 0)) as avg_sell_through_rate
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
                       AVG(total_revenue / NULLIF(booth_fee, 0)) as avg_roi
                FROM events 
                WHERE status = 'completed'
                GROUP BY event_type
                ORDER BY avg_revenue DESC
            """, conn)
            insights['event_performance'] = event_performance
            
    except Exception as e:
        st.error(f"Error generating insights: {e}")
    
    return insights

# =============== PROFESSIONAL UI COMPONENTS ===============

def theme_planning_form():
    """Professional theme and strategy planning interface"""
    st.header("Event Theme & Strategy Planning")
    st.markdown("*Plan your creative vision and business strategy for upcoming events*")
    
    # Basic event details
    st.subheader("Event Details")
    col1, col2 = st.columns(2)
    
    with col1:
        name = st.text_input("Event Name")
        event_date = st.date_input("Event Date")
        location = st.text_input("Location")
        event_type = st.selectbox("Event Type", [
            "Art Fair", "Farmers Market", "Studio Sale", "Gallery Show", 
            "Holiday Market", "Pop-up Shop", "Other"
        ])
    
    with col2:
        booth_fee = st.number_input("Booth Fee ($)", min_value=0.0, step=25.0)
        setup_time = st.time_input("Setup Time")
        expected_attendance = st.selectbox("Expected Attendance", [
            "Small (< 100 people)", "Medium (100-500)", "Large (500-1000)", "Very Large (1000+)"
        ])
        weather_backup = st.text_input("Weather Backup Plan")
    
    # Theme development
    st.subheader("Creative Theme Development")
    theme_name = st.text_input("Collection/Theme Name", 
                              help="What will you call this body of work?")
    
    col3, col4 = st.columns(2)
    with col3:
        st.markdown("**Visual Elements**")
        color_palette = st.text_area("Color Palette & Glazes", 
                                    placeholder="Describe your color scheme, specific glazes, visual mood...")
        forms_shapes = st.text_area("Forms & Shapes", 
                                   placeholder="What forms will you focus on? Why these shapes?")
        
    with col4:
        st.markdown("**Conceptual Framework**")
        inspiration = st.text_area("Theme Inspiration", 
                                  placeholder="What inspired this collection? Story behind the work...")
        theme_description = st.text_area("Artist Statement", 
                                        placeholder="How would you describe this body of work to customers?")
    
    # Target market analysis
    st.subheader("Market & Customer Strategy")
    col5, col6 = st.columns(2)
    
    with col5:
        target_customer = st.text_area("Target Customer Profile", 
                                      placeholder="Who is your ideal customer for this event? Age, interests, budget...")
        customer_needs = st.text_area("Customer Needs & Pain Points", 
                                     placeholder="What problems does your pottery solve for them?")
    
    with col6:
        price_strategy = st.text_area("Pricing Strategy", 
                                     placeholder="How will you price for this audience and venue?")
        value_proposition = st.text_area("Value Proposition", 
                                        placeholder="Why should customers choose your work over others?")
    
    # Business goals
    st.subheader("Event Goals & Success Metrics")
    col7, col8 = st.columns(2)
    
    with col7:
        revenue_goal = st.number_input("Revenue Goal ($)", min_value=0.0, step=100.0)
        pieces_goal = st.number_input("Pieces to Sell", min_value=0, step=1)
        
    with col8:
        learning_goals = st.text_area("Learning Goals", 
                                     placeholder="What do you want to learn from this event?")
        network_goals = st.text_area("Networking Goals", 
                                    placeholder="Who do you want to connect with?")
    
    # Save event
    completed = st.checkbox("Event completed - add results")
    
    if completed:
        st.subheader("Event Results")
        col9, col10 = st.columns(2)
        
        with col9:
            total_revenue = st.number_input("Total Revenue", min_value=0.0, step=0.01)
            cash_sales = st.number_input("Cash Sales", min_value=0.0, step=0.01)
            card_sales = st.number_input("Card Sales", min_value=0.0, step=0.01)
            
        with col10:
            weather_actual = st.text_input("Actual Weather")
            foot_traffic = st.selectbox("Foot Traffic", ["Light", "Moderate", "Heavy", "Excellent"])
            overall_rating = st.slider("Overall Event Rating (1-10)", 1, 10, 5)
    
    if st.button("Save Event Plan", type="primary"):
        if not name:
            st.error("Please enter an event name")
            return None
        
        event_data = {
            "name": name, "event_date": event_date, "location": location, "event_type": event_type,
            "theme": theme_name, "theme_description": theme_description, "color_palette": color_palette,
            "target_customer": target_customer, "price_strategy": price_strategy, "booth_fee": booth_fee,
            "setup_time": str(setup_time), "weather": weather_actual if completed else "",
            "foot_traffic": foot_traffic if completed else "",
            "total_revenue": total_revenue if completed else 0,
            "cash_sales": cash_sales if completed else 0,
            "card_sales": card_sales if completed else 0, "check_sales": 0,
            "discounts_given": 0, "rewards_given": 0,
            "status": "completed" if completed else "planned"
        }
        
        event_id = create_event(event_data)
        if event_id:
            st.success(f"Event plan saved successfully (ID: {event_id})")
            return event_id
    
    return None

def reflection_journal():
    """Thoughtful reflection and journaling interface"""
    st.header("Show Reflection Journal")
    st.markdown("*Capture insights and learnings from your pottery events*")
    
    # Select event to reflect on
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
        
        # Show event details for context
        with st.expander("Event Details", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Date:** {event['event_date']}")
                st.write(f"**Location:** {event['location']}")
                st.write(f"**Type:** {event['event_type']}")
                if event['theme']:
                    st.write(f"**Theme:** {event['theme']}")
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
            reflection_category = st.selectbox("Reflection Category", [
                "What Worked Well",
                "What Didn't Work", 
                "Customer Interactions",
                "Pricing Insights",
                "Display & Setup",
                "Competition Analysis",
                "Next Time Planning",
                "Unexpected Discoveries",
                "General Observations"
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
        
        # Show existing reflections
        reflections = get_reflections(event_id)
        
        if not reflections.empty:
            st.subheader("Previous Reflections")
            
            # Filter options
            col5, col6, col7 = st.columns(3)
            with col5:
                filter_category = st.selectbox("Filter by Category", 
                                             ["All"] + list(reflections['category'].unique()))
            with col6:
                show_customer_only = st.checkbox("Customer interactions only")
            with col7:
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

def business_intelligence_dashboard():
    """Clean, professional business insights dashboard"""
    st.header("Business Intelligence Dashboard")
    st.markdown("*Data-driven insights for strategic pottery business decisions*")
    
    insights = get_business_insights()
    
    if not insights:
        st.info("Complete some events with inventory tracking to see business insights.")
        return
    
    # Price point analysis
    if 'price_analysis' in insights and not insights['price_analysis'].empty:
        st.subheader("Price Point Performance")
        price_df = insights['price_analysis']
        
        # Find best performing price range
        best_range = price_df.loc[price_df['avg_sell_through_rate'].idxmax()]
        
        col1, col2 = st.columns(2)
        with col1:
            st.bar_chart(price_df.set_index('price_range')['avg_sell_through_rate'])
        with col2:
            st.metric("Best Performing Price Range", best_range['price_range'], 
                     f"{best_range['avg_sell_through_rate']:.1%} sell-through")
            st.dataframe(price_df, use_container_width=True)
    
    # Make more/less recommendations
    if 'make_more_less' in insights and not insights['make_more_less'].empty:
        st.subheader("Production Recommendations")
        recs_df = insights['make_more_less']
        
        make_more = recs_df[recs_df['recommendation'] == 'MAKE MORE']
        make_less = recs_df[recs_df['recommendation'] == 'MAKE LESS']
        
        col3, col4 = st.columns(2)
        
        with col3:
            if not make_more.empty:
                st.markdown("**🟢 MAKE MORE (High Demand)**")
                for _, item in make_more.iterrows():
                    st.write(f"• **{item['item_name']}** - {item['avg_sell_through_rate']:.1%} sell-through")
        
        with col4:
            if not make_less.empty:
                st.markdown("**🔴 MAKE LESS (Low Demand)**")
                for _, item in make_less.iterrows():
                    st.write(f"• **{item['item_name']}** - {item['avg_sell_through_rate']:.1%} sell-through")
        
        st.dataframe(recs_df, use_container_width=True)
    
    # Seasonal analysis
    if 'seasonal_analysis' in insights and not insights['seasonal_analysis'].empty:
        st.subheader("Seasonal Performance Trends")
        seasonal_df = insights['seasonal_analysis']
        
        # Group by season and show top items
        for season in ['Spring', 'Summer', 'Fall', 'Winter']:
            season_data = seasonal_df[seasonal_df['season'] == season]
            if not season_data.empty:
                st.markdown(f"**{season}**")
                top_items = season_data.head(3)
                for _, item in top_items.iterrows():
                    st.write(f"• {item['item_name']} - {item['total_sold']} sold, ${item['avg_price']:.2f} avg price")
    
    # Event type performance
    if 'event_performance' in insights and not insights['event_performance'].empty:
        st.subheader("Event Type Performance")
        event_df = insights['event_performance']
        
        col5, col6 = st.columns(2)
        with col5:
            st.bar_chart(event_df.set_index('event_type')['avg_revenue'])
            st.caption("Average Revenue by Event Type")
        
        with col6:
            # Show ROI data
            roi_data = event_df[['event_type', 'avg_roi']].dropna()
            if not roi_data.empty:
                st.bar_chart(roi_data.set_index('event_type')['avg_roi'])
                st.caption("Average ROI by Event Type")
        
        st.dataframe(event_df, use_container_width=True)

# =============== MAIN APPLICATION ===============

st.set_page_config(
    page_title="Pottery Business Notebook", 
    page_icon="📔", 
    layout="wide"
)

# Clean, professional styling
st.markdown("""
<style>
    .stMetric > div[data-testid="metric-container"] {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        padding: 15px;
        border-radius: 8px;
    }
    .stButton > button {
        background-color: #6c757d;
        color: white;
        border-radius: 5px;
        border: none;
        padding: 10px 20px;
    }
</style>
""", unsafe_allow_html=True)

# Initialize database
try:
    init_db()
except Exception as e:
    st.error(f"Database initialization error: {e}")
    st.stop()

# Simple, professional navigation
st.sidebar.title("📔 Pottery Business Notebook")
st.sidebar.markdown("*Professional pottery business management*")

menu_options = [
    "Dashboard",
    "Theme & Strategy Planning", 
    "Reflection Journal",
    "Business Intelligence",
    "Events & Shows",
    "Inventory Management"
]

menu = st.sidebar.selectbox("Navigate", menu_options)

# Main content area
if menu == "Dashboard":
    st.title("Pottery Business Overview")
    
    # Quick stats
    try:
        with closing(get_conn()) as conn:
            stats = pd.read_sql_query("""
                SELECT 
                    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_events,
                    COUNT(CASE WHEN status = 'planned' THEN 1 END) as planned_events,
                    SUM(CASE WHEN status = 'completed' THEN total_revenue ELSE 0 END) as total_revenue,
                    AVG(CASE WHEN status = 'completed' THEN total_revenue ELSE NULL END) as avg_revenue
                FROM events
            """, conn)
            
            if not stats.empty:
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Completed Events", safe_int(stats.iloc[0]['completed_events']))
                with col2:
                    st.metric("Planned Events", safe_int(stats.iloc[0]['planned_events']))
                with col3:
                    st.metric("Total Revenue", f"${safe_float(stats.iloc[0]['total_revenue']):,.2f}")
                with col4:
                    st.metric("Avg per Event", f"${safe_float(stats.iloc[0]['avg_revenue']):,.2f}")
    except:
        st.info("Complete your first event to see overview statistics.")
    
    # Recent reflections
    recent_reflections = get_reflections()
    if not recent_reflections.empty:
        st.subheader("Recent Reflections")
        for _, reflection in recent_reflections.head(3).iterrows():
            with st.expander(f"{reflection['event_name']} - {reflection['category']}"):
                st.write(reflection['content'])

elif menu == "Theme & Strategy Planning":
    theme_planning_form()

elif menu == "Reflection Journal":
    reflection_journal()

elif menu == "Business Intelligence":
    business_intelligence_dashboard()

elif menu == "Events & Shows":
    st.header("Events & Shows Management")
    events_df = get_events()
    
    if not events_df.empty:
        st.dataframe(events_df[['name', 'event_date', 'event_type', 'status', 'total_revenue']], 
                    use_container_width=True)
    else:
        st.info("No events created yet. Use 'Theme & Strategy Planning' to create your first event.")

elif menu == "Inventory Management":
    st.header("Inventory Management")
    st.info("Inventory management features available in full version.")

# Professional footer
st.sidebar.markdown("---")
st.sidebar.markdown("*Focus on your craft, track your business*")
