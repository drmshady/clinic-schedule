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
        pd.DataFrame(columns=["Name", "Title", "Shift_Pref", "Supervisor", "Sun_Session", "Vacation_Start", "Vacation_End"]).to_excel(writer, sheet_name="Doctors", index=False)
        pd.DataFrame(columns=["Clinic_Number"]).to_excel(writer, sheet_name="Clinics", index=False)
    return buffer

def generate_dates(start_date, end_date):
    date_list = []
    current = start_date
    while current <= end_date:
        # EXCLUDE FRIDAY AND SATURDAY
        if current.strftime("%A") not in ["Friday", "Saturday"]:
            date_list.append(current)
        current += timedelta(days=1)
    return date_list

def is_on_vacation(doc, current_day_name):
    # Friday is no longer needed in index, but keeping it won't break anything
    DAY_INDEX = {"Sunday": 0, "Monday": 1, "Tuesday": 2, "Wednesday": 3, "Thursday": 4, "Friday": 5}
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
            aggfunc=lambda x: ', '.join(x)
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
                display_text = (text[:20] + '..') if len(text) > 22 else text
                
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

if not uploaded_file:
    preloaded_doctors = [
        {"Name": "Dr. Amjad", "Title": "Res", "Shift_Pref": "Both", "Sup": False, "Sun_Session": "Both"},
        {"Name": "Dr. M Atef", "Title": "Cons", "Shift_Pref": "Both", "Sup": True, "Sun_Session": "None"},
        {"Name": "Dr. M Shady", "Title": "Cons", "Shift_Pref": "Both", "Sup": True, "Sun_Session": "None"},
        {"Name": "Dr. Moatez", "Title": "Spec", "Shift_Pref": "Both", "Sup": True, "Sun_Session": "None"},
        {"Name": "Dr. M Sandokji", "Title": "Cons", "Shift_Pref": "Both", "Sup": True, "Sun_Session": "None"},
        {"Name": "Dr. Abeer", "Title": "Spec", "Shift_Pref": "Both", "Sup": True, "Sun_Session": "None"},
        {"Name": "Dr. Ziad", "Title": "Res", "Shift_Pref": "Both", "Sup": False, "Sun_Session": "Both"},
        {"Name": "Dr. Sara", "Title": "Res", "Shift_Pref": "Both", "Sup": False, "Sun_Session": "Both"},
        {"Name": "Dr. Ahmed E.", "Title": "Spec", "Shift_Pref": "Both", "Sup": True, "Sun_Session": "None"},
        {"Name": "Dr. Nesam", "Title": "Cons", "Shift_Pref": "Both", "Sup": True, "Sun_Session": "None"},
        {"Name": "Dr. Ohood", "Title": "Res", "Shift_Pref": "Both", "Sup": False, "Sun_Session": "Both"},
        {"Name": "Dr. Hanin", "Title": "Spec", "Shift_Pref": "Both", "Sup": True, "Sun_Session": "None"},
        {"Name": "Dr. Asayel", "Title": "Spec", "Shift_Pref": "Both", "Sup": True, "Sun_Session": "None"},
        {"Name": "Dr. Abdullah", "Title": "Res", "Shift_Pref": "Both", "Sup": False, "Sun_Session": "Both"},
        {"Name": "Dr. Hind", "Title": "Spec", "Shift_Pref": "Both", "Sup": True, "Sun_Session": "None"},
        {"Name": "Dr. Bassam", "Title": "Spec", "Shift_Pref": "Both", "Sup": True, "Sun_Session": "None"},
        {"Name": "Dr. Tariq", "Title": "Res", "Shift_Pref": "Both", "Sup": False, "Sun_Session": "Both"},
        {"Name": "Dr. Faisel", "Title": "Res", "Shift_Pref": "Both", "Sup": False, "Sun_Session": "Both"},
        {"Name": "Dr. Roqaya", "Title": "Res", "Shift_Pref": "Both", "Sup": False, "Sun_Session": "Both"},
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

tab1, tab2, tab3 = st.tabs(["👥 Team", "🏥 Clinics", "🚀 Generate"])

with tab1:
    st.info("💡 Edit Vacations and Scientific Day preferences here.")
    edited_docs_df = st.data_editor(df_docs, num_rows="dynamic", use_container_width=True)

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
                # Logic: No Fridays (Generated dates already exclude Fri/Sat)
                current_team = day_team if shift_label == "AM" else night_team
                active_team = [doc for doc in current_team if not is_on_vacation(doc, day_name)]
                
                available_for_clinic = []
                for doc in active_team:
                    sun_pref = doc.get("Sun_Session", "None")
                    is_res = "Res" in str(doc.get("Title", ""))
                    if is_res and (sun_pref == "None" or pd.isna(sun_pref)): sun_pref = "Both"

                    if shift_label == "AM" and day_name == "Sunday" and sun_pref != "None":
                        schedule_rows.append({"Day": display_date, "SortDate": date_str, "Shift": shift_label, "Clinic": f"Sci: {sun_pref}", "Doctor": f"{doc['Name']}"})
                    else:
                        available_for_clinic.append(doc)

                random.shuffle(available_for_clinic)
                available_for_clinic.sort(key=lambda x: workload_tracker[x['Name']])

                residents_q = [d for d in available_for_clinic if not d.get('Supervisor')]
                supervisors_q = [d for d in available_for_clinic if d.get('Supervisor')]

                # 1. Fill Clinics
                for clinic in clinic_list:
                    assigned = None
                    if residents_q:
                        assigned = residents_q.pop(0)
                    elif supervisors_q:
                        assigned = supervisors_q.pop(0)
                    
                    if assigned:
                        sup_tag = " (Sup)" if assigned.get('Supervisor') else ""
                        schedule_rows.append({"Day": display_date, "SortDate": date_str, "Shift": shift_label, "Clinic": str(clinic), "Doctor": f"{assigned['Name']}{sup_tag}"})
                        workload_tracker[assigned['Name']] += 1

                # 2. Assign Remaining Supervisors to 'Supervision'
                for doc in supervisors_q:
                    schedule_rows.append({"Day": display_date, "SortDate": date_str, "Shift": shift_label, "Clinic": "Supervision", "Doctor": f"{doc['Name']}"})
                    workload_tracker[doc['Name']] += 1
                
                # 3. Assign Remaining Residents to 'Reserve'
                for doc in residents_q:
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
                st.dataframe(df_am.pivot_table(index=['SortDate', 'Day'], columns='Clinic', values='Doctor', aggfunc=lambda x: ', '.join(x)), use_container_width=True)
            with t2:
                st.dataframe(df_pm.pivot_table(index=['SortDate', 'Day'], columns='Clinic', values='Doctor', aggfunc=lambda x: ', '.join(x)), use_container_width=True)

            pdf_path = create_split_pdf(df_am, df_pm, start_d.strftime("%Y-%m-%d"), end_d.strftime("%Y-%m-%d"), clinic_list)
            with open(pdf_path, "rb") as f:
                st.download_button("📥 Download Final PDF", f, "Dental_Schedule.pdf", "application/pdf")
