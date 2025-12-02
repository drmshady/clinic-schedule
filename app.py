import streamlit as st
import pandas as pd
import random
from fpdf import FPDF
from datetime import datetime, timedelta
import io

# ==========================================
#   1. APP CONFIGURATION & STYLING
# ==========================================
st.set_page_config(
    page_title="Dental Roster Pro",
    page_icon="🦷",
    layout="wide",
    initial_sidebar_state="auto"
)

st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    h1 { font-size: 1.8rem; color: #2c3e50; }
    .stButton>button { 
        height: 3.5em; 
        border-radius: 10px; 
        width: 100%; 
        font-weight: bold;
        background-color: #2e86de; 
        color: white;
    }
    .metric-box {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 8px;
        text-align: center;
        font-weight: bold;
        border: 1px solid #e0e0e0;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
#   2. HELPER FUNCTIONS
# ==========================================

def get_empty_template():
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        pd.DataFrame(columns=[
            "Name", "Title", "Shift_Pref", "Supervisor", "Target_Load", 
            "Sun_Session", "Vacation_Start", "Vacation_End"
        ]).to_excel(writer, sheet_name="Doctors", index=False)
        pd.DataFrame(columns=["Clinic_Number"]).to_excel(writer, sheet_name="Clinics", index=False)
    return buffer

def generate_dates(start_date, end_date):
    date_list = []
    current = start_date
    while current <= end_date:
        if current.strftime("%A") not in ["Friday", "Saturday"]:
            date_list.append(current)
        current += timedelta(days=1)
    return date_list

def is_on_vacation(doc, current_day_name):
    DAY_INDEX = {"Sunday": 0, "Monday": 1, "Tuesday": 2, "Wednesday": 3, "Thursday": 4}
    v_start = doc.get("Vacation_Start")
    v_end = doc.get("Vacation_End")
    if pd.isna(v_start) or pd.isna(v_end) or v_start is None: return False
    
    start_idx = DAY_INDEX.get(v_start, -1)
    end_idx = DAY_INDEX.get(v_end, -1)
    curr_idx = DAY_INDEX.get(current_day_name, -1)
    
    if start_idx != -1 and start_idx <= curr_idx <= end_idx: return True
    return False

def create_split_pdf(df_am, df_pm, start_str, end_str, clinics):
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    
    # --- HELPER TO DRAW A TABLE ---
    def draw_table(pdf_obj, data_df, title_text, color_header):
        pdf_obj.add_page()
        pdf_obj.set_font("Arial", 'B', 16)
        pdf_obj.cell(0, 10, title_text, ln=True, align='C')
        pdf_obj.set_font("Arial", 'I', 10)
        pdf_obj.cell(0, 5, f"Week: {start_str} to {end_str}", ln=True, align='C')
        pdf_obj.ln(5)

        # Pivot Data
        pivot = data_df.pivot(index=['SortDate', 'Day'], columns='Clinic', values='Doctor')
        
        # Determine Columns
        cols = [str(c) for c in clinics]
        # Add Sci Day columns if they exist in data
        sci_cols = [c for c in pivot.columns if "Sci" in c]
        other_cols = [c for c in ["Floor/Reserve", "VACATION"] if c in pivot.columns]
        
        # Final Column Order: Clinics -> Sci -> Reserve -> Vacation
        final_cols = [c for c in cols if c in pivot.columns] + sci_cols + other_cols
        pivot = pivot[final_cols].fillna("-")
        
        # Dimensions
        w_day = 35
        w_clinic = 35
        
        # Header
        pdf_obj.set_fill_color(*color_header) # Unpack color tuple
        pdf_obj.set_text_color(255, 255, 255)
        pdf_obj.set_font("Arial", 'B', 9)
        
        pdf_obj.cell(w_day, 10, "Date", 1, 0, 'C', 1)
        for col in final_cols:
            # Adjust width for long Sci headers
            curr_w = 40 if "Sci" in col else w_clinic
            pdf_obj.cell(curr_w, 10, col, 1, 0, 'C', 1)
        pdf_obj.ln()

        # Rows
        pdf_obj.set_text_color(0, 0, 0)
        pdf_obj.set_font("Arial", size=8)
        pivot = pivot.reset_index().sort_values(['SortDate'])

        for _, row in pivot.iterrows():
            cell_height = 10
            day_text = str(row['Day']).replace("\n", " - ")
            pdf_obj.cell(w_day, cell_height, day_text, 1, 0, 'C')
            
            for col in final_cols:
                text = str(row[col])
                curr_w = 40 if "Sci" in col else w_clinic
                
                if "OFF" in text or col == "VACATION":
                     pdf_obj.set_text_color(150, 150, 150)
                     pdf_obj.cell(curr_w, cell_height, text, 1, 0, 'C')
                     pdf_obj.set_text_color(0, 0, 0)
                elif "(Sup)" in text:
                    pdf_obj.set_font("Arial", 'B', 8)
                    pdf_obj.cell(curr_w, cell_height, text, 1, 0, 'C')
                    pdf_obj.set_font("Arial", '', 8)
                else:
                    pdf_obj.cell(curr_w, cell_height, text, 1, 0, 'C')
            pdf_obj.ln()

    # --- DRAW AM TABLE ---
    # Dark Blue Header for Morning
    draw_table(pdf, df_am, "☀️ Morning Shift Schedule", (52, 73, 94))
    
    # --- DRAW PM TABLE ---
    # Dark Grey/Purple Header for Night
    draw_table(pdf, df_pm, "🌙 Evening Shift Schedule", (80, 40, 90))

    output_pdf = "Dental_Schedule_Split.pdf"
    pdf.output(output_pdf)
    return output_pdf

# ==========================================
#   3. SIDEBAR & SETUP
# ==========================================
with st.sidebar:
    st.title("⚙️ Roster Setup")
    uploaded_file = st.file_uploader("Upload Excel", type=["xlsx"])
    if not uploaded_file:
        st.info("Using Pre-loaded Team (19 Doctors)")
        st.download_button("📄 Download Template", get_empty_template(), "dental_template.xlsx")
    
    st.markdown("---")
    start_d = st.date_input("Start Date", datetime.today())
    end_d = st.date_input("End Date", datetime.today() + timedelta(days=4))

st.title("🦷 Dental Roster Pro")

# --- LOAD DATA ---
if uploaded_file:
    try:
        df_docs = pd.read_excel(uploaded_file, sheet_name="Doctors")
        df_clinics = pd.read_excel(uploaded_file, sheet_name="Clinics")
    except:
        st.error("Error reading Excel.")
        st.stop()
else:
    # PRE-LOADED DATA FROM YOUR IMAGE
    preloaded_doctors = [
        # RESIDENTS (Target 5, Default Scientific Day = Both)
        {"Name": "Dr. Amjad",       "Title": "Res", "Shift_Pref": "Both", "Sup": False, "Sun_Session": "Both"},
        {"Name": "Dr. Ziad",        "Title": "Res", "Shift_Pref": "Both", "Sup": False, "Sun_Session": "Both"},
        {"Name": "Dr. Sara",        "Title": "Res", "Shift_Pref": "Both", "Sup": False, "Sun_Session": "Both"},
        {"Name": "Dr. Ohood",       "Title": "Res", "Shift_Pref": "Both", "Sup": False, "Sun_Session": "Both"},
        {"Name": "Dr. Abdullah",    "Title": "Res", "Shift_Pref": "Both", "Sup": False, "Sun_Session": "Both"},
        {"Name": "Dr. Tariq",       "Title": "Res", "Shift_Pref": "Both", "Sup": False, "Sun_Session": "Both"},
        {"Name": "Dr. Faisel",      "Title": "Res", "Shift_Pref": "Both", "Sup": False, "Sun_Session": "Both"},
        {"Name": "Dr. Roqaya",      "Title": "Res", "Shift_Pref": "Both", "Sup": False, "Sun_Session": "Both"},
        
        # CONSULTANTS (Target 2, Supervisor)
        {"Name": "Dr. M Atef",      "Title": "Cons", "Shift_Pref": "Both", "Sup": True, "Sun_Session": "None"},
        {"Name": "Dr. M Shady",     "Title": "Cons", "Shift_Pref": "Both", "Sup": True, "Sun_Session": "None"},
        {"Name": "Dr. M Sandokji",  "Title": "Cons", "Shift_Pref": "Both", "Sup": True, "Sun_Session": "None"},
        {"Name": "Dr. Nesam",       "Title": "Cons", "Shift_Pref": "Both", "Sup": True, "Sun_Session": "None"},
        
        # SPECIALISTS (Target 5, Mix of Sup/Non-Sup)
        {"Name": "Dr. Moatez",          "Title": "Spec", "Shift_Pref": "Both", "Sup": True, "Sun_Session": "None"},
        {"Name": "Dr. Abeer",           "Title": "Spec", "Shift_Pref": "Both", "Sup": True, "Sun_Session": "None"},
        {"Name": "Dr. Ahmed Elmahlawy", "Title": "Spec", "Shift_Pref": "Both", "Sup": True, "Sun_Session": "None"},
        {"Name": "Dr. Hanin",           "Title": "Spec", "Shift_Pref": "Both", "Sup": True, "Sun_Session": "None"},
        {"Name": "Dr. Asayel",          "Title": "Spec", "Shift_Pref": "Both", "Sup": True, "Sun_Session": "None"},
        {"Name": "Dr. Hind",            "Title": "Spec", "Shift_Pref": "Both", "Sup": True, "Sun_Session": "None"},
        {"Name": "Dr. Bassam",          "Title": "Spec", "Shift_Pref": "Both", "Sup": True, "Sun_Session": "None"},
    ]
    # Normalize keys for the app
    for d in preloaded_doctors:
        d["Supervisor"] = d.pop("Sup") 
        d["Vacation_Start"] = None
        d["Vacation_End"] = None
        d["Target_Load"] = 5 if d["Title"] == "Res" else 2

    df_docs = pd.DataFrame(preloaded_doctors)
    df_clinics = pd.DataFrame([{"Clinic_Number": 15}, {"Clinic_Number": 10}, {"Clinic_Number": 9}, {"Clinic_Number": 8}])

# --- STATS ROW ---
c1, c2, c3 = st.columns(3)
c1.markdown(f"<div class='metric-box'>Doctors: {len(df_docs)}</div>", unsafe_allow_html=True)
c2.markdown(f"<div class='metric-box'>Clinics: {len(df_clinics)}</div>", unsafe_allow_html=True)
c3.markdown(f"<div class='metric-box'>Start: {start_d.strftime('%b %d')}</div>", unsafe_allow_html=True)
st.markdown("---")

# --- TABS ---
tab1, tab2, tab3 = st.tabs(["👥 Team & Scientific Day", "🏥 Clinics", "🚀 Generate"])

with tab1:
    st.info("💡 **Scientific Day:** Select 'Session 1', 'Session 2', or 'Both' for Sunday AM.")
    edited_docs_df = st.data_editor(
        df_docs, num_rows="dynamic", use_container_width=True,
        column_config={
            "Supervisor": st.column_config.CheckboxColumn("Sup?", width="small"),
            "Sun_Session": st.column_config.SelectboxColumn(
                "Sunday Sci. Day", 
                options=["None", "Session 1", "Session 2", "Both"],
                required=True,
                width="medium"
            ),
            "Shift_Pref": st.column_config.SelectboxColumn("Shift", options=["Day", "Night", "Both"], width="small"),
        }
    )

with tab2:
    edited_clinics_df = st.data_editor(df_clinics, num_rows="dynamic", use_container_width=True)

with tab3:
    if st.button("Generate Split Schedule"):
        # 1. SETUP
        doctors_db = edited_docs_df.to_dict('records')
        clinic_list = edited_clinics_df["Clinic_Number"].tolist()
        workload_tracker = {doc['Name']: 0 for doc in doctors_db}
        schedule_rows = []
        
        # 2. ASSIGN TEAMS
        day_team, night_team, flexible = [], [], []
        for doc in doctors_db:
            pref = doc.get("Shift_Pref", "Both")
            if pref == "Day": day_team.append(doc)
            elif pref == "Night": night_team.append(doc)
            else: flexible.append(doc)
            
        random.shuffle(flexible)
        for doc in flexible:
            if len(day_team) <= len(night_team): day_team.append(doc)
            else: night_team.append(doc)
            
        # 3. GENERATE
        dates = generate_dates(start_d, end_d)
        
        for d in dates:
            day_name = d.strftime("%A")
            date_str = d.strftime("%Y-%m-%d")
            display_date = f"{day_name}\n{date_str}"
            
            def process_shift(team, shift_label):
                available = []
                for doc in team:
                    if is_on_vacation(doc, day_name):
                        schedule_rows.append({"Day": display_date, "SortDate": date_str, "Shift": shift_label, "Clinic": "VACATION", "Doctor": f"{doc['Name']} (OFF)"})
                    else: available.append(doc)
                
                random.shuffle(available)
                available.sort(key=lambda x: workload_tracker[x['Name']])
                
                assigned_count = 0
                for doc in available:
                    # SCIENTIFIC DAY LOGIC
                    sun_pref = doc.get("Sun_Session", "None")
                    is_res = "Res" in str(doc.get("Title", ""))
                    
                    # Force Residents to Both if default None, otherwise respect user choice
                    if is_res and (sun_pref == "None" or pd.isna(sun_pref)):
                        sun_pref = "Both"
                    
                    if shift_label == "AM" and day_name == "Sunday" and sun_pref != "None":
                        # Display specific session
                        loc = f"Sci: {sun_pref}"
                    else:
                        if assigned_count < len(clinic_list):
                            loc = str(clinic_list[assigned_count])
                            assigned_count += 1
                            workload_tracker[doc['Name']] += 1
                        else:
                            loc = "Floor/Reserve"
                            workload_tracker[doc['Name']] += 1
                            
                    sup_lbl = " (Sup)" if doc.get("Supervisor") == True else ""
                    schedule_rows.append({"Day": display_date, "SortDate": date_str, "Shift": shift_label, "Clinic": loc, "Doctor": f"{doc['Name']} ({doc['Title']}){sup_lbl}"})

            process_shift(day_team, "AM")
            process_shift(night_team, "PM")

        # 4. DISPLAY RESULTS (SPLIT)
        final_df = pd.DataFrame(schedule_rows)
        
        # Split into Day and Night DFs
        df_am = final_df[final_df['Shift'] == 'AM']
        df_pm = final_df[final_df['Shift'] == 'PM']
        
        st.success("✅ Schedule Generated!")
        
        res_tab1, res_tab2 = st.tabs(["☀️ Morning Roster", "🌙 Evening Roster"])
        
        with res_tab1:
            st.subheader("Morning Shift (8 AM - 4 PM)")
            pivot_am = df_am.pivot(index=['SortDate', 'Day'], columns='Clinic', values='Doctor')
            st.dataframe(pivot_am, use_container_width=True)
            
        with res_tab2:
            st.subheader("Evening Shift (4 PM - 12 AM)")
            pivot_pm = df_pm.pivot(index=['SortDate', 'Day'], columns='Clinic', values='Doctor')
            st.dataframe(pivot_pm, use_container_width=True)
        
        # 5. PDF
        pdf_file = create_split_pdf(df_am, df_pm, start_d.strftime("%Y-%m-%d"), end_d.strftime("%Y-%m-%d"), clinic_list)
        with open(pdf_file, "rb") as f:
            st.download_button("📥 Download Official PDF (Split Tables)", f, "Dental_Schedule.pdf", "application/pdf")
