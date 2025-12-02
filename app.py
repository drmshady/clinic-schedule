import streamlit as st
import pandas as pd
import random
from fpdf import FPDF
from datetime import datetime, timedelta
import io

# ==========================================
#   1. APP CONFIGURATION
# ==========================================
st.set_page_config(page_title="Dental Roster Pro", page_icon="🦷", layout="wide")

st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    .stButton>button { 
        height: 3.5em; 
        border-radius: 10px; 
        width: 100%; 
        font-weight: bold;
        background-color: #2e86de; 
        color: white;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
#   2. LOGIC FUNCTIONS
# ==========================================

def get_empty_template():
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        pd.DataFrame(columns=["Name", "Title", "Shift_Pref", "Supervisor", "Supervise_Clinic", "Sun_Session", "Vacation_Start", "Vacation_End"]).to_excel(writer, sheet_name="Doctors", index=False)
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

def is_on_vacation(doc, current_date):
    """Checks if the doctor is on vacation based on calendar dates."""
    v_start = doc.get("Vacation_Start")
    v_end = doc.get("Vacation_End")
    
    if pd.isna(v_start) or v_start is None: return False
    
    # Ensure date objects are compared against date objects
    start_date = pd.to_datetime(v_start).date()
    end_date = pd.to_datetime(v_end).date()
    
    if start_date <= current_date.date() <= end_date:
        return True
    return False

def create_split_pdf(df_am, df_pm, start_str, end_str, clinics):
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    
    def draw_table(pdf_obj, data_df, title_text, color_header):
        if data_df.empty: return
        pdf_obj.add_page()
        pdf_obj.set_font("Arial", 'B', 16)
        pdf_obj.cell(0, 10, title_text, ln=True, align='C')
        pdf_obj.set_font("Arial", 'I', 10)
        pdf_obj.cell(0, 5, f"Period: {start_str} to {end_str}", ln=True, align='C')
        pdf_obj.ln(5)

        # Pivot Data
        pivot = data_df.pivot_table(
            index=['SortDate', 'Day'], 
            columns='Clinic', 
            values='Doctor', 
            aggfunc=lambda x: '\n'.join(x) # Use newline for better readability of pairs
        )
        
        # Sort Columns
        std_cols = sorted([c for c in pivot.columns if c.isdigit()], key=int)
        sci_cols = [c for c in pivot.columns if "Sci" in c]
        sup_cols = [c for c in pivot.columns if "Supervision" in c]
        other_cols = [c for c in pivot.columns if c not in std_cols + sci_cols + sup_cols]
        
        final_cols = std_cols + sup_cols + sci_cols + other_cols
        pivot = pivot[final_cols].fillna("-")
        
        # Styling
        w_day = 35
        w_col = 35
        
        pdf_obj.set_fill_color(*color_header) 
        pdf_obj.set_text_color(255, 255, 255)
        pdf_obj.set_font("Arial", 'B', 9)
        
        pdf_obj.cell(w_day, 10, "Date", 1, 0, 'C', 1)
        for col in final_cols:
            pdf_obj.cell(w_col, 10, str(col), 1, 0, 'C', 1)
        pdf_obj.ln()

        pdf_obj.set_text_color(0, 0, 0)
        pdf_obj.set_font("Arial", size=8)
        pivot = pivot.reset_index().sort_values(['SortDate'])

        for _, row in pivot.iterrows():
            pdf_obj.cell(w_day, 10, str(row['Day']), 1, 0, 'C')
            for col in final_cols:
                text = str(row[col])
                display_text = text.replace('\n', ' | ') # Replace newline with separator for single-line PDF cell
                
                if len(display_text) > 22: display_text = display_text[:20] + '..'
                
                if "OFF" in text or col == "VACATION":
                    pdf_obj.set_text_color(150, 150, 150)
                elif "(Sup)" in text and "Supervision" not in col:
                    pdf_obj.set_font("Arial", 'B', 8)
                
                pdf_obj.cell(w_col, 10, display_text, 1, 0, 'C')
                pdf_obj.set_text_color(0, 0, 0)
                pdf_obj.set_font("Arial", '', 8)
            pdf_obj.ln()

    draw_table(pdf, df_am, "MORNING SCHEDULE", (52, 73, 94))
    draw_table(pdf, df_pm, "NIGHT CLINIC SCHEDULE", (80, 40, 90))

    output_pdf = "Dental_Schedule_Final.pdf"
    pdf.output(output_pdf)
    return output_pdf

# ==========================================
#   3. UI & SETUP
# ==========================================
st.sidebar.title("⚙️ Setup")
uploaded_file = st.sidebar.file_uploader("Upload Excel", type=["xlsx"])

# --- Pre-loaded Data (Initial state for the app) ---
if not uploaded_file:
    preloaded_doctors = [
        {"Name": "Dr. Amjad", "Title": "Res", "Shift_Pref": "Both", "Sup": False, "Sun_Session": "Both", "Supervise_Clinic": None},
        {"Name": "Dr. M Atef", "Title": "Cons", "Shift_Pref": "Both", "Sup": True, "Sun_Session": "None", "Supervise_Clinic": 8}, # Assigned to Clinic 8
        {"Name": "Dr. M Shady", "Title": "Cons", "Shift_Pref": "Both", "Sup": True, "Sun_Session": "None", "Supervise_Clinic": None}, 
        {"Name": "Dr. Moatez", "Title": "Spec", "Shift_Pref": "Both", "Sup": True, "Sun_Session": "None", "Supervise_Clinic": None}, 
        {"Name": "Dr. M Sandokji", "Title": "Cons", "Shift_Pref": "Both", "Sup": True, "Sun_Session": "None", "Supervise_Clinic": 9}, # Assigned to Clinic 9
        {"Name": "Dr. Abeer", "Title": "Spec", "Shift_Pref": "Both", "Sup": True, "Sun_Session": "None", "Supervise_Clinic": None},
        {"Name": "Dr. Ziad", "Title": "Res", "Shift_Pref": "Both", "Sup": False, "Sun_Session": "Both", "Supervise_Clinic": None},
        {"Name": "Dr. Sara", "Title": "Res", "Shift_Pref": "Both", "Sup": False, "Sun_Session": "Both", "Supervise_Clinic": None},
        {"Name": "Dr. Ahmed E.", "Title": "Spec", "Shift_Pref": "Both", "Sup": True, "Sun_Session": "None", "Supervise_Clinic": None},
        {"Name": "Dr. Nesam", "Title": "Cons", "Shift_Pref": "Both", "Sup": True, "Sun_Session": "None", "Supervise_Clinic": None},
        {"Name": "Dr. Ohood", "Title": "Res", "Shift_Pref": "Both", "Sup": False, "Sun_Session": "Both", "Supervise_Clinic": None},
        {"Name": "Dr. Hanin", "Title": "Spec", "Shift_Pref": "Both", "Sup": True, "Sun_Session": "None", "Supervise_Clinic": None},
        {"Name": "Dr. Asayel", "Title": "Spec", "Shift_Pref": "Both", "Sup": True, "Sun_Session": "None", "Supervise_Clinic": None},
        {"Name": "Dr. Abdullah", "Title": "Res", "Shift_Pref": "Both", "Sup": False, "Sun_Session": "Both", "Supervise_Clinic": None},
        {"Name": "Dr. Hind", "Title": "Spec", "Shift_Pref": "Both", "Sup": True, "Sun_Session": "None", "Supervise_Clinic": None},
        {"Name": "Dr. Bassam", "Title": "Spec", "Shift_Pref": "Both", "Sup": True, "Sun_Session": "None", "Supervise_Clinic": None},
        {"Name": "Dr. Tariq", "Title": "Res", "Shift_Pref": "Both", "Sup": False, "Sun_Session": "Both", "Supervise_Clinic": None},
        {"Name": "Dr. Faisel", "Title": "Res", "Shift_Pref": "Both", "Sup": False, "Sun_Session": "Both", "Supervise_Clinic": None},
        {"Name": "Dr. Roqaya", "Title": "Res", "Shift_Pref": "Both", "Sup": False, "Sun_Session": "Both", "Supervise_Clinic": None},
    ]
    for d in preloaded_doctors:
        d["Supervisor"] = d.pop("Sup")
        d["Vacation_Start"] = None
        d["Vacation_End"] = None
        d["Target_Load"] = 5 if d["Title"] == "Res" else 2
    
    df_docs = pd.DataFrame(preloaded_doctors)
    df_clinics = pd.DataFrame([{"Clinic_Number": 8}, {"Clinic_Number": 9}, {"Clinic_Number": 10}, {"Clinic_Number": 15}])
else:
    df_docs = pd.read_excel(uploaded_file, sheet_name="Doctors")
    df_clinics = pd.read_excel(uploaded_file, sheet_name="Clinics")

st.sidebar.markdown("---")
start_d = st.sidebar.date_input("Start Date", datetime.today())
end_d = st.sidebar.date_input("End Date", datetime.today() + timedelta(days=6))

st.title("🦷 Dental Roster Pro")

tab1, tab2, tab3 = st.tabs(["👥 Team Settings", "🏥 Clinics", "🚀 Generate"])

with tab1:
    st.info("💡 To assign a Supervisor to a specific clinic, enter the **Clinic Number** (8, 9, 10, or 15) in the **Supervise_Clinic** column.")
    # UPDATED COLUMN CONFIG WITH DROPDOWNS & DATE PICKERS
    edited_docs_df = st.data_editor(
        df_docs, 
        num_rows="dynamic", 
        use_container_width=True,
        column_config={
            "Supervisor": st.column_config.CheckboxColumn("Supervisor?", width="small"),
            "Supervise_Clinic": st.column_config.NumberColumn("Supervise_Clinic", width="small", min_value=8, max_value=15, step=1, help="Specific clinic to supervise, e.g., 15"),
            "Shift_Pref": st.column_config.SelectboxColumn("Shift Preference", options=["Day", "Night", "Both"], width="medium", required=True),
            "Sun_Session": st.column_config.SelectboxColumn("Sunday Status", options=["None", "Session 1", "Session 2", "Both"], width="medium", required=True),
            "Vacation_Start": st.column_config.DateColumn("Vacation_Start", format="YYYY-MM-DD", help="Start date of vacation block"),
            "Vacation_End": st.column_config.DateColumn("Vacation_End", format="YYYY-MM-DD", help="End date of vacation block"),
            "Title": st.column_config.TextColumn("Role", disabled=True),
        }
    )

with tab2:
    edited_clinics_df = st.data_editor(df_clinics, num_rows="dynamic", use_container_width=True)

with tab3:
    if st.button("Generate Schedule"):
        doctors_db = edited_docs_df.to_dict('records')
        clinic_list = edited_clinics_df["Clinic_Number"].tolist()
        workload_tracker = {doc['Name']: 0 for doc in doctors_db}
        schedule_rows = []
        
        day_team = [d for d in doctors_db if d.get('Shift_Pref') in ['Day', 'Both']]
        night_team = [d for d in doctors_db if d.get('Shift_Pref') in ['Night', 'Both']]

        dates = generate_dates(start_d, end_d)

        for d in dates:
            day_name = d.strftime("%A")
            date_str = d.strftime("%Y-%m-%d")
            display_date = f"{day_name}\n{date_str}"

            for shift_label in ["AM", "PM"]:
                current_team = day_team if shift_label == "AM" else night_team
                
                # Filter out those on vacation
                active_team = [doc for doc in current_team if not is_on_vacation(doc, d)]
                
                available_for_clinic = []
                for doc in active_team:
                    sun_pref = doc.get("Sun_Session", "None")
                    is_res = "Res" in str(doc.get("Title", ""))
                    if is_res and (sun_pref == "None" or pd.isna(sun_pref)): sun_pref = "Both"

                    if shift_label == "AM" and day_name == "Sunday" and sun_pref != "None":
                        schedule_rows.append({"Day": display_date, "SortDate": date_str, "Shift": shift_label, "Clinic": f"Sci: {sun_pref}", "Doctor": f"{doc['Name']}"})
                    else:
                        available_for_clinic.append(doc)

                # Sort for fairness before processing
                random.shuffle(available_for_clinic)
                available_for_clinic.sort(key=lambda x: workload_tracker[x['Name']])

                # Separate Roles
                residents_q = [d for d in available_for_clinic if not d.get('Supervisor')]
                supervisors_q = [d for d in available_for_clinic if d.get('Supervisor')]
                
                # Track clinics that need to be filled by the general pool
                unassigned_clinics = set(clinic_list)
                
                # --- PRIORITY 1: PAIRED SUPERVISION ---
                for clinic_num in clinic_list:
                    clinic_str = str(clinic_num)
                    
                    # Find dedicated Supervisor for this clinic
                    dedicated_sup_list = [d for d in supervisors_q if str(d.get('Supervise_Clinic', '')) == clinic_str]
                    
                    if dedicated_sup_list and residents_q:
                        # 1. Take a Resident (Worker)
                        worker = residents_q.pop(0)
                        # 2. Take the Dedicated Supervisor
                        supervisor = dedicated_sup_list.pop(0)
                        supervisors_q.remove(supervisor) # Remove from general sup pool
                        
                        # 3. Assign PAIR to the clinic
                        pair_label = f"{worker['Name']} | {supervisor['Name']} (Sup)"
                        schedule_rows.append({"Day": display_date, "SortDate": date_str, "Shift": shift_label, "Clinic": clinic_str, "Doctor": pair_label})
                        workload_tracker[worker['Name']] += 1
                        workload_tracker[supervisor['Name']] += 1
                        unassigned_clinics.remove(clinic_num)

                # --- PRIORITY 2: FILL REMAINING CLINICS ---
                
                # Create a temporary pool of remaining supervisors/residents for general fill
                general_pool = residents_q + supervisors_q
                random.shuffle(general_pool)
                
                # Fill remaining clinics with the general pool
                for clinic_num in list(unassigned_clinics):
                    clinic_str = str(clinic_num)
                    if general_pool:
                        assigned = general_pool.pop(0)
                        sup_tag = " (Sup)" if assigned.get('Supervisor') else ""
                        schedule_rows.append({"Day": display_date, "SortDate": date_str, "Shift": shift_label, "Clinic": clinic_str, "Doctor": f"{assigned['Name']}{sup_tag}"})
                        workload_tracker[assigned['Name']] += 1
                        
                # --- PRIORITY 3: RESERVE / SUPERVISION ---
                
                # Recalculate remaining supervisors (who are now in general_pool)
                remaining_supervisors = [d for d in general_pool if d.get('Supervisor')]
                remaining_residents = [d for d in general_pool if not d.get('Supervisor')]
                
                # Assign Remaining Supervisors to 'Supervision'
                for doc in remaining_supervisors:
                    schedule_rows.append({"Day": display_date, "SortDate": date_str, "Shift": shift_label, "Clinic": "Supervision", "Doctor": f"{doc['Name']}"})
                    workload_tracker[doc['Name']] += 1
                
                # Assign Remaining Residents to 'Reserve'
                for doc in remaining_residents:
                    schedule_rows.append({"Day": display_date, "SortDate": date_str, "Shift": shift_label, "Clinic": "Floor/Reserve", "Doctor": f"{doc['Name']}"})
                    workload_tracker[doc['Name']] += 1

        final_df = pd.DataFrame(schedule_rows)
        if final_df.empty:
            st.warning("No shifts generated. Check date range.")
        else:
            df_am = final_df[final_df['Shift'] == 'AM']
            df_pm = final_df[final_df['Shift'] == 'PM']

            st.success("✅ Schedule Generated Successfully!")
            
            t1, t2 = st.tabs(["☀️ Day Schedule", "🌙 Night Schedule"])
            with t1:
                st.dataframe(df_am.pivot_table(index=['SortDate', 'Day'], columns='Clinic', values='Doctor', aggfunc=lambda x: '\n'.join(x)), use_container_width=True)
            with t2:
                st.dataframe(df_pm.pivot_table(index=['SortDate', 'Day'], columns='Clinic', values='Doctor', aggfunc=lambda x: '\n'.join(x)), use_container_width=True)

            pdf_path = create_split_pdf(df_am, df_pm, start_d.strftime("%Y-%m-%d"), end_d.strftime("%Y-%m-%d"), clinic_list)
            with open(pdf_path, "rb") as f:
                st.download_button("📥 Download Final PDF", f, "Dental_Schedule.pdf", "application/pdf")
