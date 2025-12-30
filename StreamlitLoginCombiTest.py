import streamlit as st
from datetime import datetime
import time
import json
import os
from supabase import create_client, Client

# -----------------------------
# CONFIG
# -----------------------------
USERS = {
    "Abbie": "1111",
    "Michael": "2222",
    "Sam": "3333",
    "Jonny": "4444",
}

REFRESH_SECONDS = 10  # check every 10 seconds
SUPABASE_URL = "https://qexngbpvashjiperqiga.supabase.co"

# =================
# SUPABASE FUNCTIONS
# =================
def get_supabase_client(api_key: str) -> Client:
    """Create and return a Supabase client."""
    return create_client(SUPABASE_URL, api_key)

def add_order(supabase: Client, entry_id, user, item, min_part, max_part, price, status):
    """Insert a new order into Supabase."""
    data = {
        "entry_id": entry_id,
        "name": user,
        "item": item,
        "min": min_part,
        "max": max_part,
        "price": float(price) if price else 0.0,
        "status": status,
        "participants": [user],
        "created_at": datetime.now().isoformat()
    }
    supabase.table("orders").insert(data).execute()

# def add_order(supabase: Client):
#     """Insert a new order into Supabase."""
#     data = {
#         "created_at": datetime.now().isoformat(),
#         "entry_id": "Test entry id",
#         "name": "Me",
#         "price": 0.0,
#         "min": 1,
#         "max": 2,
#         "status": "solo",
#         "participants": "me",
#         "item": "item test",
#     }
#     supabase.table("orders").insert(data).execute()

def get_orders(supabase: Client):
    """Fetch all orders from Supabase."""
    response = supabase.table("orders").select("*").execute()
    return response.data if response.data else []

def get_orders_filter(supabase: Client, item_name: str):
    """Fetch all orders for a specific item."""
    response = supabase.table("orders").select("*").eq("item", item_name).execute()
    return response.data if response.data else []

def add_participant(supabase: Client, entry_id: str, user: str):
    """Add a participant to an order by updating the participants array."""
    response = supabase.table("orders").select("participants").eq("entry_id", entry_id).execute()
    if response.data:
        current_participants = response.data[0].get("participants", []) or []
        if user not in current_participants:
            current_participants.append(user)
            supabase.table("orders").update({"participants": current_participants}).eq("entry_id", entry_id).execute()

def get_last_update(supabase: Client):
    """Return the latest timestamp from Supabase."""
    response = supabase.table("orders").select("created_at").order("created_at", desc=True).limit(1).execute()
    return response.data[0]["created_at"] if response.data else ""

def clear_orders(supabase: Client):
    """Delete all orders from Supabase."""
    supabase.table("orders").delete().neq("entry_id", "").execute()


# Initialize Supabase client
if "supabase" not in st.session_state:
    # Try to get API key from secrets, otherwise prompt user
    api_key = None
    try:
        api_key = st.secrets["supabase"]["key"]
    except Exception:
        pass

    if not api_key:
        api_key = st.text_input("Enter your Supabase API Key:", type="password", key="api_key_input")
        if api_key:
            st.session_state.supabase = get_supabase_client(api_key)
            st.rerun()
    else:
        #st.session_state.supabase = get_supabase_client(api_key)
        st.session_state.supabase = create_client(SUPABASE_URL, api_key)

# -----------------------------
# APP SETUP
# -----------------------------

# Load menu
with open("menu_items.json", "r", encoding="utf-8") as f:
    menu_items = json.load(f)

# Ensure each menu item has a "type" field; default to "main" if missing
updated = False
for mi in menu_items:
    if "type" not in mi:
        mi["type"] = "main"
        updated = True
if updated:
    # write back the augmented menu to keep the JSON in sync
    with open("menu_items.json", "w", encoding="utf-8") as f:
        json.dump(menu_items, f, indent=2, ensure_ascii=False)
        
st.set_page_config(page_title="Chinese Menu Order", layout="wide")
if "orders" not in st.session_state:
    st.session_state.orders = {}

# Persistent order index to create unique order IDs without datetime
if "order_index" not in st.session_state:
    st.session_state.order_index = 0

# Initialize session state
if "share_open" not in st.session_state:
    st.session_state.share_open = {}          # Tracks which popup is open
if "share_ranges" not in st.session_state:
    st.session_state.share_ranges = {}        # Stores min/max per item
if "participants" not in st.session_state:
    st.session_state.participants = {}        # Tracks participants per item


#st.set_page_config(page_title="Group Ordering", layout="centered")
#init_db()

if "user" not in st.session_state:
    st.session_state.user = None
if "last_db_update" not in st.session_state:
    st.session_state.last_db_update = ""
if "last_refresh_time" not in st.session_state:
    st.session_state.last_refresh_time = time.time()

# -----------------------------
# LOGIN
# -----------------------------
if st.session_state.user is None:
    st.title("Login")

    name = st.selectbox("Who are you?", list(USERS.keys()))
    code = st.text_input("Your code", type="password")
   
    #Practice writing the secrets value, not for use!
    #st.write(st.secrets["supabase"]["url"])

    if st.button("Continue"):
        if USERS[name] == code:
            st.session_state.user = name
            st.rerun()
        else:
            st.error("Wrong code")

    st.stop()

# -----------------------------
# TIMED DB-CHECK REFRESH (Supabase-aware)
# -----------------------------
def _parse_iso_to_dt(s):
    if not s:
        return None
    try:
        # handle 'Z' suffix by removing it if necessary
        s2 = s.rstrip("Z")
        return datetime.fromisoformat(s2)
    except Exception:
        return None

now = time.time()
if now - st.session_state.last_refresh_time > REFRESH_SECONDS:
    st.session_state.last_refresh_time = now
    st.rerun()

    # # If Supabase client is available, prefer checking the DB
    # if "supabase" in st.session_state and st.session_state.supabase:
    #     try:
    #         last_update = get_last_update(st.session_state.supabase)  # should return ISO timestamp string
    #         if last_update:
    #             prev_dt = _parse_iso_to_dt(st.session_state.last_db_update)
    #             curr_dt = _parse_iso_to_dt(last_update)
    #             # If we can parse both as datetimes, compare them as datetimes
    #             changed = False
    #             if prev_dt and curr_dt:
    #                 changed = curr_dt > prev_dt
    #             else:
    #                 # fallback to string compare if parsing failed
    #                 changed = (last_update != st.session_state.last_db_update)

    #             if changed:
    #                 st.session_state.last_db_update = last_update
    #                 st.rerun()
    #     except Exception as e:
    #         # Log and continue — do not crash the app because of a transient Supabase problem
    #         st.warning(f"Supabase sync check failed: {e}")
    # else:
    #     # Fallback: check in-memory orders for changes (useful before user has entered API key)
    #     latest = ""
    #     for entry in st.session_state.get("orders", {}).values():
    #         created = entry.get("created") or entry.get("created_at") or ""
    #         if created and (latest == "" or created > latest):
    #             latest = created
    #     if latest and latest != st.session_state.last_db_update:
    #         st.session_state.last_db_update = latest
    #         st.rerun()

# -----------------------------
# MAIN APP
# -----------------------------
st.success(f"Logged in as {st.session_state.user}")
page = st.sidebar.radio("Navigation", ["Menu", "Basket"])

if page == "Menu":
    st.header("Menu")

    for item in menu_items:
        name = item["name"]
        price = item["price"]
        type = item["type"]
        st.subheader(name)
        st.write(f"Price: £{price}")
        
    #Show the single button
        if st.button(f"Order '{name}' for myself", key=f"{name}_solo_btn"):
    # Create a new shared order entry using a persistent session index
            entry_id = f"{name}_({st.session_state.order_index})"
            st.session_state.order_index += 1
            st.session_state.orders[entry_id] = {
            "name": name,
            "price":price,
            "min": int(1),
            "max": int(1),
            "status":"solo",
            "participants": ["You"],
            "created": datetime.now().isoformat()
        }
    #Create a new order in the database, needs to also create a line in participants for just that one person
            add_order(st.session_state.supabase, entry_id,st.session_state.user, name, int(1), int(1), price, "solo")
            st.rerun()
    # Show Share button
        if not st.session_state.share_open.get(name, False):
            if st.button(f"Share '{name}'", key=f"{name}_share_btn"):
                st.session_state.share_open[name] = True
                st.rerun()
        else:
            # Popup: select min/max range
            min_val, max_val = st.select_slider(
                "Select min/max participants",
                options=[str(i) for i in range(1, 11)],
                value=("1", "4"),
                key=f"{name}_slider"
            )
            #Cancel Button to close popup without creating shared order. Need to rerun in order to refresh
            if st.button("Cancel",icon="❌", key=f"{name}_cancel_btn"):
                # Close popup
                st.session_state.share_open[name] = False
                st.rerun()
            #Can create buttons within an if statement to be able to do stuff with their output
            if st.button(f"Confirm sharing for '{name}'", key=f"{name}_confirm_btn"):
                # Close popup
                st.session_state.share_open[name] = False

                # Create a new shared order entry using a persistent session index
                entry_id = f"{name}_({st.session_state.order_index})"
                #Add this to the database
                add_order(st.session_state.supabase, entry_id,st.session_state.user, name,int(min_val), int(max_val) , price, "shared")
                st.rerun()

        #Try and get orders to show the live ones
        orders = get_orders_filter(st.session_state.supabase,name)

        #Show live trackers for any shared orders for this item
        if orders:
            for order in orders:
                min_part = order.get("min")
                max_part = order.get("max")
                entry_id = order.get("entry_id")
                current_participants = order.get("participants", [])
                slots_left = max_part - len(current_participants)
                st.write(f"Shared order: {entry_id} — Participants ({len(current_participants)}/{max_part}, min {min_part}): {', '.join(current_participants)}")

                if slots_left > 0:
                    if st.button(f"Join '{name}' ({entry_id})", key=f"{entry_id}_join_btn"):    
                        #Add new participant to the participants table in databae
                        add_participant(st.session_state.supabase, entry_id, st.session_state.user)
                        st.rerun()

# -----------------------------
# LIVE ORDERS VIEW
# -----------------------------

#Setup the Basket Page
elif page == "Basket":
    st.header("Basket")
    st.subheader("Current orders (live)")

    orders = get_orders(st.session_state.supabase)
    person_totals = {}
    total_price = 0.0

    if orders:
        for order in orders:
            user = order.get("name")
            item = order.get("item")
            count = len(order.get("participants", []))
            min =  order.get("min")
            max =  order.get("max")
            participants = order.get("participants", []) or []
            st.write(f"**{item}** for {min}-{max} participants. Currently ({len(participants)}): {', '.join(participants)}")
            price = float(order.get("price", 0) or 0)
            owner = order.get("name")
            total_price += price
            if participants:
                # Split price evenly across participants
                share = price / len(participants) if len(participants) > 0 else price
                for p in participants:
                    person_totals[p] = person_totals.get(p, 0.0) + share
            else:
                # Attribute whole price to owner if participants empty
                if owner:
                    person_totals[owner] = person_totals.get(owner, 0.0) + price
                else:
                    # fallback: attribute to 'Unknown'
                    person_totals["Unknown"] = person_totals.get("Unknown", 0.0) + price
        st.write(f"**Total across all orders: £{total_price:.2f}**")
        st.subheader("Totals per person")
        for person, amt in person_totals.items():
            st.write(f"**{person}**: £{amt:.2f}")
    else:
        st.write("_No orders yet_")

    st.write(f"_Last updated: {st.session_state.last_db_update}_")

    # -----------------------------
    # ADMIN
    # -----------------------------
    with st.expander("Admin"):
        if st.button("Clear all orders"):
            clear_orders(st.session_state.supabase)
            st.session_state.last_db_update = ""
            st.rerun()

        if st.button("Log out"):
            st.session_state.clear()
            st.rerun()
