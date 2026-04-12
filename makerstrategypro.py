import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime, date
import numpy as np

# =============== DATABASE CONNECTION ===============

@st.cache_resource
def get_client() -> Client:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

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

def to_df(data) -> pd.DataFrame:
    if not data:
        return pd.DataFrame()
    return pd.DataFrame(data)

def uid():
    """Get current user's ID."""
    return st.session_state.user.id

# =============== AUTHENTICATION ===============

def login_page():
    st.markdown("""
    <div class="main-header">
        <h1>🏺 Maker Strategy Pro</h1>
        <p>Strategic planning and business insights for artists.</p>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["Sign In", "Create Account"])

    with tab1:
        st.subheader("Welcome back!")
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")

        if st.button("Sign In", type="primary", key="signin_btn"):
            if not email or not password:
                st.error("Please enter your email and password.")
            else:
                try:
                    sb = get_client()
                    response = sb.auth.sign_in_with_password({
                        "email": email,
                        "password": password
                    })
                    st.session_state.user = response.user
                    st.session_state.session = response.session
                    st.success("Signed in successfully!")
                    st.rerun()
                except Exception as e:
                    st.error("Invalid email or password. Please try again.")

    with tab2:
        st.subheader("Create your free account")
        new_email = st.text_input("Email", key="signup_email")
        new_password = st.text_input("Password (min 6 characters)", 
                                     type="password", key="signup_password")
        confirm_password = st.text_input("Confirm Password", 
                                         type="password", key="confirm_password")

        if st.button("Create Account", type="primary", key="signup_btn"):
            if not new_email or not new_password:
                st.error("Please fill in all fields.")
            elif len(new_password) < 6:
                st.error("Password must be at least 6 characters.")
            elif new_password != confirm_password:
                st.error("Passwords do not match.")
            else:
                try:
                    sb = get_client()
                    response = sb.auth.sign_up({
                        "email": new_email,
                        "password": new_password
                    })
                    st.session_state.user = response.user
                    st.session_state.session = response.session
                    st.success("Account created! Welcome to Maker Strategy Pro!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not create account: {e}")

def logout():
    try:
        sb = get_client()
        sb.auth.sign_out()
    except:
        pass
    st.session_state.user = None
    st.session_state.session = None
    st.rerun()

def check_auth():
    """Returns True if user is logged in."""
    if "user" not in st.session_state:
        st.session_state.user = None
        st.session_state.session = None
    return st.session_state.user is not None

# =============== ITEM FUNCTIONS ===============

def upsert_item(row: dict):
    try:
        sb = get_client()
        now = datetime.utcnow().isoformat()
        payload = {
            "sku": safe_string(row.get("sku")),
            "name": safe_string(row.get("name")),
            "category": safe_string(row.get("category")),
            "clay_body": safe_string(row.get("clay_body")),
            "glaze": safe_string(row.get("glaze")),
            "size": safe_string(row.get("size")),
            "price": safe_float(row.get("price")),
            "qty_on_hand": safe_float(row.get("qty_on_hand")),
            "location": safe_string(row.get("location")),
            "notes": safe_string(row.get("notes")),
            "image_path": safe_string(row.get("image_path")),
            "updated_at": now,
            "user_id": uid(),
        }
        existing = sb.table("items").select("id") \
            .eq("sku", payload["sku"]).eq("user_id", uid()).execute()
        if existing.data:
            sb.table("items").update(payload).eq("sku", payload["sku"]) \
                .eq("user_id", uid()).execute()
        else:
            payload["created_at"] = now
            sb.table("items").insert(payload).execute()
    except Exception as e:
        st.error(f"Error saving item: {e}")

def fetch_items_df(search: str = "") -> pd.DataFrame:
    try:
        sb = get_client()
        if search:
            q = safe_string(search).strip()
            result = sb.table("items").select("*") \
                .eq("user_id", uid()).ilike("name", f"%{q}%").execute()
            df = to_df(result.data)
            for field in ["sku", "category", "glaze", "clay_body"]:
                r2 = sb.table("items").select("*") \
                    .eq("user_id", uid()).ilike(field, f"%{q}%").execute()
                if r2.data:
                    df = pd.concat([df, to_df(r2.data)]).drop_duplicates(subset="id")
            return df
        else:
            result = sb.table("items").select("*") \
                .eq("user_id", uid()).order("updated_at", desc=True).execute()
            return to_df(result.data)
    except Exception as e:
        st.error(f"Database error: {e}")
        return pd.DataFrame()

def delete_item(item_id):
    try:
        sb = get_client()
        sb.table("stock_moves").delete().eq("item_id", item_id).eq("user_id", uid()).execute()
        sb.table("items").delete().eq("id", item_id).eq("user_id", uid()).execute()
    except Exception as e:
        st.error(f"Error deleting item: {e}")

def record_move(item_id: int, move_type: str, quantity: float, reference: str = ""):
    try:
        sb = get_client()
        now = datetime.utcnow().isoformat()
        sb.table("stock_moves").insert({
            "item_id": safe_int(item_id),
            "move_type": safe_string(move_type),
            "quantity": safe_float(quantity),
            "reference": safe_string(reference),
            "moved_at": now,
            "user_id": uid(),
        }).execute()
        item = sb.table("items").select("qty_on_hand") \
            .eq("id", item_id).eq("user_id", uid()).execute()
        if item.data:
            new_qty = safe_float(item.data[0]["qty_on_hand"]) + safe_float(quantity)
            sb.table("items").update({"qty_on_hand": new_qty, "updated_at": now}) \
                .eq("id", item_id).eq("user_id", uid()).execute()
    except Exception as e:
        st.error(f"Error recording move: {e}")

# =============== EVENT FUNCTIONS ===============

def create_event(event_data):
    try:
        sb = get_client()
        now = datetime.utcnow().isoformat()
        payload = {
            "name": safe_string(event_data.get("name")),
            "event_date": str(event_data.get("event_date", "")),
            "location": safe_string(event_data.get("location")),
            "event_type": safe_string(event_data.get("event_type")),
            "theme": safe_string(event_data.get("theme")),
            "theme_description": safe_string(event_data.get("theme_description")),
            "change_goal": safe_string(event_data.get("change_goal")),
            "color_palette": safe_string(event_data.get("color_palette")),
            "target_customer": safe_string(event_data.get("target_customer")),
            "price_strategy": safe_string(event_data.get("price_strategy")),
            "booth_fee": safe_float(event_data.get("booth_fee")),
            "setup_time": safe_string(event_data.get("setup_time")),
            "weather": safe_string(event_data.get("weather")),
            "foot_traffic": safe_string(event_data.get("foot_traffic")),
            "total_revenue": safe_float(event_data.get("total_revenue")),
            "cash_sales": safe_float(event_data.get("cash_sales")),
            "card_sales": safe_float(event_data.get("card_sales")),
            "check_sales": safe_float(event_data.get("check_sales")),
            "discounts_given": safe_float(event_data.get("discounts_given")),
            "rewards_given": safe_float(event_data.get("rewards_given")),
            "status": safe_string(event_data.get("status", "planned")),
            "created_at": now,
            "updated_at": now,
            "user_id": uid(),
        }
        result = sb.table("events").insert(payload).execute()
        if result.data:
            return result.data[0]["id"]
        return None
    except Exception as e:
        st.error(f"Error creating event: {e}")
        return None

def update_event(event_id, event_data):
    try:
        sb = get_client()
        now = datetime.utcnow().isoformat()
        payload = {
            "name": safe_string(event_data.get("name")),
            "event_date": str(event_data.get("event_date", "")),
            "location": safe_string(event_data.get("location")),
            "event_type": safe_string(event_data.get("event_type")),
            "theme": safe_string(event_data.get("theme")),
            "theme_description": safe_string(event_data.get("theme_description")),
            "change_goal": safe_string(event_data.get("change_goal")),
            "color_palette": safe_string(event_data.get("color_palette")),
            "target_customer": safe_string(event_data.get("target_customer")),
            "price_strategy": safe_string(event_data.get("price_strategy")),
            "booth_fee": safe_float(event_data.get("booth_fee")),
            "setup_time": safe_string(event_data.get("setup_time")),
            "weather": safe_string(event_data.get("weather")),
            "foot_traffic": safe_string(event_data.get("foot_traffic")),
            "total_revenue": safe_float(event_data.get("total_revenue")),
            "cash_sales": safe_float(event_data.get("cash_sales")),
            "card_sales": safe_float(event_data.get("card_sales")),
            "check_sales": safe_float(event_data.get("check_sales")),
            "discounts_given": safe_float(event_data.get("discounts_given")),
            "rewards_given": safe_float(event_data.get("rewards_given")),
            "status": safe_string(event_data.get("status", "planned")),
            "updated_at": now,
        }
        sb.table("events").update(payload) \
            .eq("id", safe_int(event_id)).eq("user_id", uid()).execute()
        return True
    except Exception as e:
        st.error(f"Error updating event: {e}")
        return False

def get_events():
    try:
        sb = get_client()
        result = sb.table("events").select("*") \
            .eq("user_id", uid()).order("event_date", desc=True).execute()
        return to_df(result.data)
    except Exception as e:
        st.error(f"Error loading events: {e}")
        return pd.DataFrame()

def delete_event(event_id):
    try:
        sb = get_client()
        sb.table("event_inventory").delete() \
            .eq("event_id", event_id).eq("user_id", uid()).execute()
        sb.table("event_reflections").delete() \
            .eq("event_id", event_id).eq("user_id", uid()).execute()
        sb.table("event_environment").delete() \
            .eq("event_id", event_id).eq("user_id", uid()).execute()
        sb.table("events").delete() \
            .eq("id", event_id).eq("user_id", uid()).execute()
        return True
    except Exception as e:
        st.error(f"Error deleting event: {e}")
        return False

# =============== EVENT INVENTORY FUNCTIONS ===============

def add_event_inventory(event_id, sku, name, brought, sold, price):
    try:
        sb = get_client()
        existing = sb.table("event_inventory").select("id") \
            .eq("event_id", safe_int(event_id)) \
            .eq("item_sku", safe_string(sku)) \
            .eq("user_id", uid()).execute()
        payload = {
            "event_id": safe_int(event_id),
            "item_sku": safe_string(sku),
            "item_name": safe_string(name),
            "quantity_brought": safe_int(brought),
            "quantity_sold": safe_int(sold),
            "price_at_event": safe_float(price),
            "user_id": uid(),
        }
        if existing.data:
            sb.table("event_inventory").update(payload) \
                .eq("id", existing.data[0]["id"]).execute()
        else:
            sb.table("event_inventory").insert(payload).execute()
    except Exception as e:
        st.error(f"Error adding event inventory: {e}")

def get_event_inventory(event_id):
    try:
        sb = get_client()
        result = sb.table("event_inventory").select("*") \
            .eq("event_id", safe_int(event_id)).eq("user_id", uid()).execute()
        return to_df(result.data)
    except Exception as e:
        st.error(f"Error loading event inventory: {e}")
        return pd.DataFrame()

def delete_event_inventory_row(inventory_id):
    try:
        sb = get_client()
        sb.table("event_inventory").delete() \
            .eq("id", inventory_id).eq("user_id", uid()).execute()
    except Exception as e:
        st.error(f"Error deleting inventory row: {e}")

# =============== REFLECTION FUNCTIONS ===============

def add_reflection(event_id, category, content, 
                   customer_interaction=False, price_point_insight=False):
    try:
        sb = get_client()
        sb.table("event_reflections").insert({
            "event_id": safe_int(event_id),
            "category": safe_string(category),
            "content": safe_string(content),
            "customer_interaction": int(bool(customer_interaction)),
            "price_point_insight": int(bool(price_point_insight)),
            "created_at": datetime.utcnow().isoformat(),
            "user_id": uid(),
        }).execute()
    except Exception as e:
        st.error(f"Error adding reflection: {e}")

def get_reflections(event_id=None):
    try:
        sb = get_client()
        if event_id:
            result = sb.table("event_reflections").select("*") \
                .eq("event_id", safe_int(event_id)) \
                .eq("user_id", uid()) \
                .order("created_at", desc=True).execute()
            return to_df(result.data)
        else:
            result = sb.table("event_reflections") \
                .select("*, events(name, event_date)") \
                .eq("user_id", uid()) \
                .order("created_at", desc=True).execute()
            df = to_df(result.data)
            if not df.empty and "events" in df.columns:
                df["event_name"] = df["events"].apply(
                    lambda x: x.get("name", "") if isinstance(x, dict) else "")
                df["event_date"] = df["events"].apply(
                    lambda x: x.get("event_date", "") if isinstance(x, dict) else "")
                df = df.drop(columns=["events"])
            return df
    except Exception as e:
        st.error(f"Error loading reflections: {e}")
        return pd.DataFrame()

def delete_reflection(reflection_id):
    try:
        sb = get_client()
        sb.table("event_reflections").delete() \
            .eq("id", reflection_id).eq("user_id", uid()).execute()
    except Exception as e:
        st.error(f"Error deleting reflection: {e}")

# =============== ENVIRONMENT FUNCTIONS ===============

def add_environment_data(event_id, environment_data):
    try:
        sb = get_client()
        now = datetime.utcnow().isoformat()
        payload = {
            "event_id": safe_int(event_id),
            "neighboring_vendor_left": safe_string(environment_data.get("neighboring_vendor_left")),
            "neighboring_vendor_right": safe_string(environment_data.get("neighboring_vendor_right")),
            "booth_location": safe_string(environment_data.get("booth_location")),
            "foot_traffic_pattern": safe_string(environment_data.get("foot_traffic_pattern")),
            "customer_demographics": safe_string(environment_data.get("customer_demographics")),
            "competition_notes": safe_string(environment_data.get("competition_notes")),
            "pricing_observations": safe_string(environment_data.get("pricing_observations")),
            "created_at": now,
            "user_id": uid(),
        }
        existing = sb.table("event_environment").select("id") \
            .eq("event_id", safe_int(event_id)).eq("user_id", uid()).execute()
        if existing.data:
            sb.table("event_environment").update(payload) \
                .eq("event_id", safe_int(event_id)).eq("user_id", uid()).execute()
        else:
            sb.table("event_environment").insert(payload).execute()
    except Exception as e:
        st.error(f"Error adding environment data: {e}")

def get_environment_data(event_id):
    try:
        sb = get_client()
        result = sb.table("event_environment").select("*") \
            .eq("event_id", safe_int(event_id)).eq("user_id", uid()).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        st.error(f"Error loading environment data: {e}")
        return None

# =============== BUSINESS INSIGHTS ===============

def get_business_insights():
    insights = {}
    try:
        sb = get_client()
        inv_df = to_df(sb.table("event_inventory").select("*")
                       .eq("user_id", uid()).execute().data)
        evt_df = to_df(sb.table("events").select("*")
                       .eq("user_id", uid()).execute().data)

        if inv_df.empty:
            return insights

        for col in ["quantity_brought", "quantity_sold", "price_at_event"]:
            inv_df[col] = pd.to_numeric(inv_df[col], errors="coerce").fillna(0)

        inv_df = inv_df[inv_df["quantity_brought"] > 0].copy()
        inv_df["sell_through"] = inv_df["quantity_sold"] / inv_df["quantity_brought"]
        inv_df["revenue"] = inv_df["quantity_sold"] * inv_df["price_at_event"]

        def price_range(p):
            if p < 20: return "Under $20"
            elif p < 30: return "$20-30"
            elif p < 40: return "$30-40"
            elif p < 50: return "$40-50"
            elif p < 75: return "$50-75"
            else: return "$75+"

        inv_df["price_range"] = inv_df["price_at_event"].apply(price_range)
        insights["price_analysis"] = inv_df.groupby("price_range").agg(
            items_in_range=("id", "count"),
            total_sold=("quantity_sold", "sum"),
            avg_sell_through_rate=("sell_through", "mean"),
            total_revenue=("revenue", "sum")
        ).reset_index().sort_values("avg_sell_through_rate", ascending=False)

        make_more_less = inv_df.groupby("item_name").agg(
            events_brought_to=("event_id", "nunique"),
            total_brought=("quantity_brought", "sum"),
            total_sold=("quantity_sold", "sum"),
            avg_sell_through_rate=("sell_through", "mean"),
            total_revenue=("revenue", "sum")
        ).reset_index()
        make_more_less = make_more_less[make_more_less["events_brought_to"] >= 2].copy()

        def recommend(r):
            if r > 0.8: return "MAKE MORE"
            elif r > 0.5: return "GOOD"
            elif r > 0.2: return "REVIEW"
            else: return "MAKE LESS"

        if not make_more_less.empty:
            make_more_less["recommendation"] = make_more_less["avg_sell_through_rate"].apply(recommend)
            insights["make_more_less"] = make_more_less.sort_values(
                "avg_sell_through_rate", ascending=False)

        if not evt_df.empty:
            completed = evt_df[evt_df["status"] == "completed"].copy()
            if not completed.empty:
                completed["event_date"] = pd.to_datetime(completed["event_date"], errors="coerce")
                completed["month"] = completed["event_date"].dt.month

                def season(m):
                    if m in [12, 1, 2]: return "Winter"
                    elif m in [3, 4, 5]: return "Spring"
                    elif m in [6, 7, 8]: return "Summer"
                    else: return "Fall"

                completed["season"] = completed["month"].apply(season)
                merged = inv_df.merge(completed[["id", "season"]], 
                                     left_on="event_id", right_on="id")
                if not merged.empty:
                    seasonal = merged.groupby(["season", "item_name"]).agg(
                        total_sold=("quantity_sold", "sum"),
                        avg_price=("price_at_event", "mean"),
                        avg_sell_through_rate=("sell_through", "mean")
                    ).reset_index()
                    insights["seasonal_analysis"] = seasonal[
                        seasonal["total_sold"] > 0].sort_values(
                        ["season", "total_sold"], ascending=[True, False])

                for col in ["total_revenue", "booth_fee"]:
                    completed[col] = pd.to_numeric(completed[col], errors="coerce").fillna(0)
                completed["profit"] = completed["total_revenue"] - completed["booth_fee"]
                completed["roi"] = completed.apply(
                    lambda r: r["total_revenue"] / r["booth_fee"] 
                    if r["booth_fee"] > 0 else None, axis=1)
                insights["event_performance"] = completed.groupby("event_type").agg(
                    total_events=("id", "count"),
                    avg_revenue=("total_revenue", "mean"),
                    avg_profit=("profit", "mean"),
                    avg_roi=("roi", "mean")
                ).reset_index().sort_values("avg_revenue", ascending=False)

    except Exception as e:
        st.error(f"Error generating insights: {e}")
    return insights

# =============== ABOUT & HELP ===============

def about_section():
    st.header("About Maker Strategy Pro")
    st.markdown("""
    ### Strategic Planning for Creative Entrepreneurs

    Maker Strategy Pro was designed by **Alford Wayman of Creek Road Pottery LLC**
    917 Creek Road, Laceyville, PA 18623 — www.creekroadpottery.com

    At the heart of Maker Strategy Pro is one fundamental question:
    **"What change are you trying to make?"**

    **Key Features:**
    - 🎯 **Strategic Event Planning** — Plan events with intention
    - 📊 **Business Insights Dashboard** — Data-driven production recommendations
    - 📝 **Event Reflection Journal** — Capture learnings from each event
    - 📦 **Inventory Management** — Track your pieces and stock levels

    ---
    **Built for artists, by artists.** Focus on your craft, grow your business.
    """)

def help_section():
    st.header("Help & User Guide")
    with st.expander("Quick Start Guide", expanded=True):
        st.markdown("""
        1. **Create your account** — Sign up with email and password
        2. **Strategic Event Planning** — Create an event, answer "What change am I trying to make?"
        3. **Inventory Management** — Add your pieces with SKUs and pricing
        4. **Event Management** — Record what you brought and sold
        5. **Event Reflection Journal** — Capture insights while fresh
        6. **Business Insights** — Get make more/less recommendations
        """)
    with st.expander("How to Read Insights"):
        st.markdown("""
        - **MAKE MORE** → >80% sell-through — high demand
        - **GOOD** → 50-80% sell-through — solid performers
        - **REVIEW** → 20-50% sell-through — consider changes
        - **MAKE LESS** → <20% sell-through — low demand

        You need at least **2 completed events** with inventory data for insights to appear.
        """)
    with st.expander("Your Data & Privacy"):
        st.markdown("""
        - Your data is private — no other user can see it
        - Data is stored securely in the cloud
        - You can access your data from any device by logging in
        - Deleting an event removes all related inventory and reflections
        """)
    st.info("Use insights to inform decisions, but always stay true to your artistic vision.")

# =============== UI COMPONENTS ===============

def strategic_event_planning():
    st.header("Strategic Event Planning")
    st.markdown("*Plan your creative vision and business strategy*")

    events_df = get_events()
    edit_mode = False
    existing_event = None

    if not events_df.empty:
        with st.expander("Edit Existing Event", expanded=False):
            event_options = ["Create New Event"] + [
                f"{row['name']} - {row['event_date']}" 
                for _, row in events_df.iterrows()]
            selected_option = st.selectbox("Select Event", event_options)
            if selected_option != "Create New Event":
                edit_mode = True
                event_idx = event_options.index(selected_option) - 1
                existing_event = events_df.iloc[event_idx]
                st.info(f"Editing: {existing_event['name']}")

    def ev(field, default=""):
        if edit_mode and existing_event is not None:
            val = existing_event.get(field)
            return val if pd.notna(val) and val is not None else default
        return default

    st.subheader("Event Information")
    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input("Event Name", value=ev("name"))
        try:
            default_date = pd.to_datetime(ev("event_date")).date() if edit_mode else date.today()
        except:
            default_date = date.today()
        event_date = st.date_input("Event Date", value=default_date)
        location = st.text_input("Location", value=ev("location"))
        event_type_options = ["Art Fair", "Farmers Market", "Studio Sale", "Gallery Show",
                              "Holiday Market", "Pop-up Shop", "Commission Show", 
                              "Online Sale", "Other"]
        et = ev("event_type", "Art Fair")
        event_type_idx = event_type_options.index(et) if et in event_type_options else 0
        event_type = st.selectbox("Event Type", event_type_options, index=event_type_idx)
    with col2:
        booth_fee = st.number_input("Booth Fee ($)", min_value=0.0, step=25.0,
                                   value=safe_float(ev("booth_fee")))
        setup_time = st.text_input("Setup Time", value=ev("setup_time"))
        st.selectbox("Expected Attendance",
            ["Small (< 100)", "Medium (100-500)", 
             "Large (500-1000)", "Very Large (1000+)"])
        st.number_input("Revenue Goal ($)", min_value=0.0, step=100.0)

    st.subheader("Strategic Intent")
    change_goal = st.text_area("What change are you trying to make?",
                              value=ev("change_goal"),
                              placeholder="What do you want to achieve? How does it fit your artistic/business growth?",
                              height=100)

    st.subheader("Creative Direction")
    col3, col4 = st.columns(2)
    with col3:
        theme_name = st.text_input("Collection/Theme Name", value=ev("theme"))
        theme_description = st.text_area("Theme Description", value=ev("theme_description"),
                                        placeholder="Describe the creative vision...")
        color_palette = st.text_area("Color Palette & Glazes", value=ev("color_palette"),
                                    placeholder="Specific glazes, color combinations...")
    with col4:
        target_customer = st.text_area("Target Customer", value=ev("target_customer"),
                                      placeholder="Who is your ideal customer?")
        price_strategy = st.text_area("Pricing Strategy", value=ev("price_strategy"),
                                     placeholder="How will you price for this audience?")
        st.text_area("What Makes Your Work Special?",
                    placeholder="What sets your pottery apart?")

    completed = st.checkbox("Event completed - add results",
                           value=(ev("status") == "completed"))
    weather_actual, foot_traffic, total_revenue = "", "Moderate", 0.0
    cash_sales, card_sales, change_achieved = 0.0, 0.0, ""

    if completed:
        st.subheader("Event Results")
        col5, col6 = st.columns(2)
        with col5:
            total_revenue = st.number_input("Total Revenue ($)", min_value=0.0, step=0.01,
                                           value=safe_float(ev("total_revenue")))
            cash_sales = st.number_input("Cash Sales ($)", min_value=0.0, step=0.01,
                                        value=safe_float(ev("cash_sales")))
            card_sales = st.number_input("Card Sales ($)", min_value=0.0, step=0.01,
                                        value=safe_float(ev("card_sales")))
        with col6:
            weather_actual = st.text_input("Actual Weather", value=ev("weather"))
            ft_options = ["Light", "Moderate", "Heavy", "Excellent"]
            ft_val = ev("foot_traffic", "Moderate")
            ft_idx = ft_options.index(ft_val) if ft_val in ft_options else 1
            foot_traffic = st.selectbox("Foot Traffic", ft_options, index=ft_idx)
            change_achieved = st.text_area(
                "Did you achieve the change you were seeking?",
                placeholder="Reflect on your progress toward your change goal...")

    button_label = "Update Event" if edit_mode else "Save Event Plan"
    if st.button(button_label, type="primary"):
        if not name:
            st.error("Please enter an event name")
            return None

        event_data = {
            "name": name, "event_date": event_date, "location": location,
            "event_type": event_type, "theme": theme_name,
            "theme_description": theme_description, "change_goal": change_goal,
            "color_palette": color_palette, "target_customer": target_customer,
            "price_strategy": price_strategy, "booth_fee": booth_fee,
            "setup_time": setup_time,
            "weather": weather_actual if completed else "",
            "foot_traffic": foot_traffic if completed else "",
            "total_revenue": total_revenue if completed else 0,
            "cash_sales": cash_sales if completed else 0,
            "card_sales": card_sales if completed else 0,
            "check_sales": 0, "discounts_given": 0, "rewards_given": 0,
            "status": "completed" if completed else "planned"
        }

        if edit_mode:
            success = update_event(existing_event["id"], event_data)
            if success:
                st.success(f"Event '{name}' updated successfully!")
                if completed and change_achieved:
                    add_reflection(existing_event["id"], "Change Achievement", change_achieved)
                st.rerun()
        else:
            event_id = create_event(event_data)
            if event_id:
                st.success(f"Event plan saved! (ID: {event_id})")
                if completed and change_achieved:
                    add_reflection(event_id, "Change Achievement", change_achieved)
                return event_id
    return None

def reflection_journal():
    st.header("Event Reflection Journal")
    st.markdown("*Capture insights and learnings from your events*")

    events_df = get_events()
    if events_df.empty:
        st.info("No events found. Create an event first to start journaling.")
        return

    event_options = [f"{row['name']} - {row['event_date']}" 
                    for _, row in events_df.iterrows()]
    selected_event = st.selectbox("Select Event to Reflect On", event_options)

    if selected_event:
        event_idx = event_options.index(selected_event)
        event = events_df.iloc[event_idx]
        event_id = event["id"]

        st.subheader(f"Reflecting on: {event['name']}")
        with st.expander("Event Context", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Date:** {event['event_date']}")
                st.write(f"**Location:** {event['location']}")
                st.write(f"**Type:** {event['event_type']}")
                if event.get("theme"): st.write(f"**Theme:** {event['theme']}")
                if event.get("change_goal"): st.write(f"**Change Goal:** {event['change_goal']}")
            with col2:
                if event["status"] == "completed":
                    rev = safe_float(event["total_revenue"])
                    fee = safe_float(event["booth_fee"])
                    st.write(f"**Revenue:** ${rev:.2f}")
                    st.write(f"**Booth Fee:** ${fee:.2f}")
                    st.write(f"**Profit:** ${rev - fee:.2f}")

        st.subheader("Add New Reflection")
        col3, col4 = st.columns(2)
        with col3:
            reflection_category = st.selectbox("Reflection Type", [
                "What Worked Well", "What Didn't Work",
                "Customer Interactions & Feedback", "Pricing Observations",
                "Display & Setup Insights", "Competition & Market Analysis",
                "Next Time Planning", "Creative Discoveries",
                "Business Learning", "Change Progress"
            ])
            customer_interaction = st.checkbox("Customer interaction note")
            price_insight = st.checkbox("Contains pricing insights")
        with col4:
            reflection_content = st.text_area("Reflection Content", height=150,
                placeholder="What did you observe? What did you learn?")

        if st.button("Save Reflection") and reflection_content:
            add_reflection(event_id, reflection_category, reflection_content,
                          customer_interaction, price_insight)
            st.success("Reflection saved")
            st.rerun()

        st.subheader("Event Environment")
        env = get_environment_data(event_id)
        with st.expander("Track Event Environment & Context", expanded=False):
            col5, col6 = st.columns(2)
            with col5:
                left_vendor = st.text_input("Left Neighbor",
                    value=safe_string((env or {}).get("neighboring_vendor_left")))
                right_vendor = st.text_input("Right Neighbor",
                    value=safe_string((env or {}).get("neighboring_vendor_right")))
                booth_location = st.text_input("Booth Location",
                    value=safe_string((env or {}).get("booth_location")))
            with col6:
                traffic_pattern = st.text_area("Foot Traffic Pattern",
                    value=safe_string((env or {}).get("foot_traffic_pattern")))
                demographics = st.text_area("Customer Demographics",
                    value=safe_string((env or {}).get("customer_demographics")))
            competition = st.text_area("Competition Notes",
                value=safe_string((env or {}).get("competition_notes")))
            pricing_obs = st.text_area("Pricing Observations",
                value=safe_string((env or {}).get("pricing_observations")))
            if st.button("Save Environment Data"):
                add_environment_data(event_id, {
                    "neighboring_vendor_left": left_vendor,
                    "neighboring_vendor_right": right_vendor,
                    "booth_location": booth_location,
                    "foot_traffic_pattern": traffic_pattern,
                    "customer_demographics": demographics,
                    "competition_notes": competition,
                    "pricing_observations": pricing_obs
                })
                st.success("Environment data saved")

        reflections = get_reflections(event_id)
        if not reflections.empty:
            st.subheader("Previous Reflections")
            col7, col8, col9 = st.columns(3)
            with col7:
                filter_category = st.selectbox("Filter by Type",
                    ["All"] + list(reflections["category"].unique()))
            with col8:
                show_customer_only = st.checkbox("Customer interactions only")
            with col9:
                show_pricing_only = st.checkbox("Pricing insights only")

            filtered = reflections.copy()
            if filter_category != "All":
                filtered = filtered[filtered["category"] == filter_category]
            if show_customer_only:
                filtered = filtered[filtered["customer_interaction"] == 1]
            if show_pricing_only:
                filtered = filtered[filtered["price_point_insight"] == 1]

            for _, reflection in filtered.iterrows():
                date_str = reflection["created_at"][:10] if reflection.get("created_at") else ""
                flags = []
                if reflection.get("customer_interaction"): flags.append("Customer")
                if reflection.get("price_point_insight"): flags.append("Pricing")
                title = f"{reflection['category']} - {date_str}"
                if flags: title += f" | {' | '.join(flags)}"
                with st.expander(title):
                    st.write(reflection["content"])

def business_insights_dashboard():
    st.header("Business Insights Dashboard")
    st.markdown("*Data-driven insights for strategic business decisions*")

    insights = get_business_insights()
    if not insights:
        st.info("Complete some events with inventory tracking to see business insights.")
        return

    if "price_analysis" in insights and not insights["price_analysis"].empty:
        st.subheader("Price Point Performance")
        price_df = insights["price_analysis"]
        col1, col2 = st.columns(2)
        with col1:
            st.bar_chart(price_df.set_index("price_range")["avg_sell_through_rate"])
            st.caption("Sell-Through Rate by Price Range")
        with col2:
            best = price_df.loc[price_df["avg_sell_through_rate"].idxmax()]
            st.metric("Best Performing Price Range", best["price_range"],
                     f"{best['avg_sell_through_rate']:.1%} sell-through")
            if best["avg_sell_through_rate"] > 0.7:
                st.success(f"Focus more inventory in the {best['price_range']} range!")
            else:
                st.info(f"Consider experimenting with the {best['price_range']} range")
        st.dataframe(price_df, use_container_width=True)

    if "make_more_less" in insights and not insights["make_more_less"].empty:
        st.subheader("Production Strategy Recommendations")
        recs_df = insights["make_more_less"]
        col3, col4, col5 = st.columns(3)
        with col3:
            st.markdown("**MAKE MORE**")
            st.caption("High demand (>80% sell-through)")
            more = recs_df[recs_df["recommendation"] == "MAKE MORE"]
            if not more.empty:
                for _, item in more.iterrows():
                    st.write(f"• **{item['item_name']}** - {item['avg_sell_through_rate']:.1%}")
            else:
                st.write("No high-demand items yet")
        with col4:
            st.markdown("**REVIEW**")
            st.caption("Moderate performance (20-80%)")
            review = recs_df[recs_df["recommendation"] == "REVIEW"]
            if not review.empty:
                for _, item in review.head(3).iterrows():
                    st.write(f"• **{item['item_name']}** - {item['avg_sell_through_rate']:.1%}")
        with col5:
            st.markdown("**MAKE LESS**")
            st.caption("Lower demand (<20% sell-through)")
            less = recs_df[recs_df["recommendation"] == "MAKE LESS"]
            if not less.empty:
                for _, item in less.iterrows():
                    st.write(f"• **{item['item_name']}** - {item['avg_sell_through_rate']:.1%}")
            else:
                st.write("All items performing well!")
        st.dataframe(
            recs_df[["item_name", "events_brought_to", "avg_sell_through_rate",
                     "total_revenue", "recommendation"]],
            use_container_width=True)

    if "seasonal_analysis" in insights and not insights["seasonal_analysis"].empty:
        st.subheader("Seasonal Performance Trends")
        seasonal_df = insights["seasonal_analysis"]
        for season in ["Spring", "Summer", "Fall", "Winter"]:
            season_data = seasonal_df[seasonal_df["season"] == season]
            if not season_data.empty:
                with st.expander(f"{season} - Top Items"):
                    for _, item in season_data.head(5).iterrows():
                        st.write(f"• **{item['item_name']}** - {item['total_sold']} sold, "
                                f"${item['avg_price']:.2f} avg, "
                                f"{item['avg_sell_through_rate']:.1%} sell-through")

    if "event_performance" in insights and not insights["event_performance"].empty:
        st.subheader("Event Type Performance")
        event_df = insights["event_performance"]
        col6, col7 = st.columns(2)
        with col6:
            st.bar_chart(event_df.set_index("event_type")["avg_revenue"])
            st.caption("Average Revenue by Event Type")
        with col7:
            st.bar_chart(event_df.set_index("event_type")["avg_profit"])
            st.caption("Average Profit by Event Type")
        st.dataframe(event_df, use_container_width=True)

def inventory_management():
    st.header("Inventory Management")
    st.markdown("*Track your pottery pieces and stock levels*")

    col1, col2 = st.columns([3, 1])
    with col1:
        search_query = st.text_input("Search inventory",
            placeholder="Search by name, SKU, category, glaze...")
    with col2:
        if st.button("Add New Item", type="primary"):
            st.session_state["show_item_form"] = True

    if st.session_state.get("show_item_form", False):
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
                    upsert_item({"sku": sku, "name": name, "category": category,
                                 "clay_body": clay_body, "glaze": glaze, "size": size,
                                 "price": price, "qty_on_hand": qty_on_hand,
                                 "location": location, "notes": notes})
                    st.success("Item saved successfully")
                    st.session_state["show_item_form"] = False
                    st.rerun()
                else:
                    st.error("SKU and Name are required")
        with col6:
            if st.button("Cancel"):
                st.session_state["show_item_form"] = False
                st.rerun()

    items_df = fetch_items_df(search_query)
    if not items_df.empty:
        st.subheader("Current Inventory")
        qty = pd.to_numeric(items_df["qty_on_hand"], errors="coerce").fillna(0)
        prc = pd.to_numeric(items_df["price"], errors="coerce").fillna(0)
        col7, col8, col9, col10 = st.columns(4)
        with col7: st.metric("Total Items", len(items_df))
        with col8: st.metric("Total Pieces", int(qty.sum()))
        with col9: st.metric("Total Value", f"${(qty * prc).sum():.2f}")
        with col10: st.metric("Low Stock Items", len(items_df[qty <= 5]))

        display_cols = [c for c in
            ["sku", "name", "category", "clay_body", "glaze", "price", "qty_on_hand", "location"]
            if c in items_df.columns]
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
                reference = st.text_input("Reference/Reason",
                    placeholder="e.g., 'Completed firing'")
            if st.button("Record Stock Movement") and quantity_change != 0:
                record_move(item["id"], "adjustment", quantity_change, reference)
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

    event_options = [f"{row['name']} - {row['event_date']}" 
                    for _, row in events_df.iterrows()]
    selected_event = st.selectbox("Select Event to Manage", event_options)

    if selected_event:
        event_idx = event_options.index(selected_event)
        event = events_df.iloc[event_idx]
        event_id = int(event["id"])

        st.subheader(f"Managing: {event['name']}")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.write(f"**Date:** {event['event_date']}")
            st.write(f"**Location:** {event['location']}")
            st.write(f"**Type:** {event['event_type']}")
        with col2:
            st.write(f"**Status:** {event['status']}")
            if safe_float(event.get("booth_fee")) > 0:
                st.write(f"**Booth Fee:** ${safe_float(event['booth_fee']):.2f}")
        with col3:
            if event["status"] == "completed":
                rev = safe_float(event["total_revenue"])
                fee = safe_float(event["booth_fee"])
                st.write(f"**Revenue:** ${rev:.2f}")
                st.write(f"**Profit:** ${rev - fee:.2f}")

        with st.expander("Danger Zone", expanded=False):
            st.warning("Delete this event and all related data")
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                confirm_delete = st.checkbox("I understand this cannot be undone")
            with col_d2:
                if st.button("Delete Event", type="secondary"):
                    if confirm_delete:
                        if delete_event(event_id):
                            st.success("Event deleted successfully!")
                            st.rerun()
                    else:
                        st.error("Please check the confirmation box first")

        st.subheader("Event Inventory")
        items_df = fetch_items_df()
        if not items_df.empty:
            st.markdown("**Add Items to Event:**")
            selected_items = st.multiselect("Select items to add",
                options=items_df["sku"].tolist(),
                format_func=lambda x: f"{x} - {items_df[items_df['sku']==x]['name'].iloc[0]}")
            if selected_items:
                for sku in selected_items:
                    item = items_df[items_df["sku"] == sku].iloc[0]
                    col4, col5, col6, col7 = st.columns(4)
                    with col4: st.write(f"**{item['name']}**")
                    with col5: brought = st.number_input("Brought", min_value=0, key=f"brought_{sku}")
                    with col6: sold = st.number_input("Sold", min_value=0, key=f"sold_{sku}")
                    with col7: price = st.number_input("Price", min_value=0.0,
                                                       value=safe_float(item["price"]),
                                                       key=f"price_{sku}")
                    if st.button(f"Add {sku} to Event", key=f"add_{sku}"):
                        add_event_inventory(event_id, sku, item["name"], brought, sold, price)
                        st.success(f"Added {item['name']} to event")
                        st.rerun()

        event_inventory = get_event_inventory(event_id)
        if not event_inventory.empty:
            st.markdown("**Current Event Inventory:**")
            ei = event_inventory.copy()
            for col in ["quantity_brought", "quantity_sold", "price_at_event"]:
                ei[col] = pd.to_numeric(ei[col], errors="coerce").fillna(0)
            ei["sell_through_rate"] = (ei["quantity_sold"] /
                                       ei["quantity_brought"].replace(0, 1)) * 100
            ei["revenue"] = ei["quantity_sold"] * ei["price_at_event"]
            st.dataframe(ei, use_container_width=True)

            with st.expander("Delete Inventory Items"):
                for _, row in ei.iterrows():
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.write(f"{row['item_name']} - Brought: {row['quantity_brought']}, "
                                f"Sold: {row['quantity_sold']}")
                    with c2:
                        if st.button("Delete", key=f"del_inv_{row['id']}"):
                            delete_event_inventory_row(row["id"])
                            st.success("Deleted")
                            st.rerun()

            col8, col9, col10, col11 = st.columns(4)
            with col8: st.metric("Total Brought", int(ei["quantity_brought"].sum()))
            with col9: st.metric("Total Sold", int(ei["quantity_sold"].sum()))
            with col10:
                overall = (ei["quantity_sold"].sum() /
                          max(ei["quantity_brought"].sum(), 1)) * 100
                st.metric("Overall Sell-Through", f"{overall:.1f}%")
            with col11:
                st.metric("Inventory Revenue", f"${ei['revenue'].sum():.2f}")

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

# =============== AUTH GATE ===============

if not check_auth():
    login_page()
    st.stop()

# =============== MAIN APP (authenticated users only) ===============

st.markdown("""
<div class="main-header">
    <h1>🏺 Maker Strategy Pro</h1>
    <p>Strategic planning and business insights for artists.</p>
</div>
""", unsafe_allow_html=True)

# Sidebar with user info and logout
st.sidebar.title("Navigation")
st.sidebar.markdown(f"👤 **{st.session_state.user.email}**")
if st.sidebar.button("Sign Out"):
    logout()

menu_options = [
    "Strategic Event Planning", "Dashboard", "Event Reflection Journal",
    "Business Insights", "Event Management", "Inventory Management", "About", "Help"
]
menu = st.sidebar.selectbox("Go to", menu_options)

if "show_item_form" not in st.session_state:
    st.session_state["show_item_form"] = False

if menu == "Strategic Event Planning":
    strategic_event_planning()
elif menu == "Dashboard":
    st.header("Overview Dashboard")
    try:
        sb = get_client()
        events_df = to_df(sb.table("events").select("*").eq("user_id", uid()).execute().data)
        item_count = len(sb.table("items").select("id").eq("user_id", uid()).execute().data or [])

        if not events_df.empty:
            events_df["total_revenue"] = pd.to_numeric(
                events_df["total_revenue"], errors="coerce").fillna(0)
            completed = events_df[events_df["status"] == "completed"]
            planned = events_df[events_df["status"] == "planned"]
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1: st.metric("Items in Inventory", item_count)
            with col2: st.metric("Completed Events", len(completed))
            with col3: st.metric("Planned Events", len(planned))
            with col4: st.metric("Total Revenue", f"${completed['total_revenue'].sum():,.2f}")
            with col5:
                avg = completed["total_revenue"].mean() if not completed.empty else 0
                st.metric("Avg per Event", f"${avg:,.2f}")
        else:
            st.info("No events yet. Start by creating your first event.")
    except Exception as e:
        st.error(f"Error loading dashboard: {e}")

    st.subheader("Recent Activity")
    recent_events = get_events().head(5)
    if not recent_events.empty:
        st.markdown("**Recent Events:**")
        for _, event in recent_events.iterrows():
            icon = "✅" if event["status"] == "completed" else "📅"
            st.write(f"{icon} **{event['name']}** - {event['event_date']} ({event['status']})")

    recent_reflections = get_reflections().head(3)
    if not recent_reflections.empty:
        st.markdown("**Recent Reflections:**")
        for _, reflection in recent_reflections.iterrows():
            event_name = reflection.get("event_name", "Unknown Event")
            with st.expander(f"{event_name} - {reflection['category']}"):
                content = reflection["content"]
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
st.sidebar.markdown("Focus on your craft, grow your business")
