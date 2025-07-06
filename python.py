import streamlit as st
import pandas as pd
from datetime import date

# Initialize session state for data persistence
if 'patients' not in st.session_state:
    st.session_state.patients = pd.DataFrame(
        columns=["ID", "Name", "Age", "Medical History", "Status", "Assigned Bed", "Priority", "Admit Date"]
    )
if 'beds' not in st.session_state:
    st.session_state.beds = pd.DataFrame(columns=["Bed ID", "Status"])
    for i in range(1, 21):
        new_bed = pd.DataFrame({"Bed ID": [f"Bed {i}"], "Status": ["Available"]})
        st.session_state.beds = pd.concat([st.session_state.beds, new_bed], ignore_index=True)

USER_ROLES = {
    "admin": {"password": "admin123", "role": "Admin"},
    "doctor": {"password": "doctor123", "role": "Doctor"},
    "nurse": {"password": "nurse123", "role": "Nurse"},
    "reception": {"password": "reception123", "role": "Receptionist"}
}

def authenticate_user(username, password):
    if username in USER_ROLES and USER_ROLES[username]["password"] == password:
        st.session_state.role = USER_ROLES[username]["role"]
        return True
    return False

def assign_beds_to_waiting_patients():
    # Emergency > Medium > Low, but Emergency can bump admitted Medium/Low
    priority_map = {"Emergency": 1, "Medium": 2, "Low": 3}
    waiting = st.session_state.patients[st.session_state.patients["Status"] == "Waiting"].copy()
    if waiting.empty:
        return

    # Sort waiting patients: Emergency first, then Medium, then Low, then by ID (FIFO)
    waiting["PriorityValue"] = waiting["Priority"].map(priority_map)
    waiting = waiting.sort_values(["PriorityValue", "ID"])

    for idx, patient in waiting.iterrows():
        available_beds = st.session_state.beds[st.session_state.beds["Status"] == "Available"]["Bed ID"].tolist()
        if available_beds:
            # Assign bed if available
            bed_id = available_beds[0]
            st.session_state.patients.at[idx, "Status"] = "Admitted"
            st.session_state.patients.at[idx, "Assigned Bed"] = bed_id
            st.session_state.patients.at[idx, "Admit Date"] = str(date.today())
            st.session_state.beds.loc[st.session_state.beds["Bed ID"] == bed_id, "Status"] = "Occupied"
        elif patient["Priority"] == "Emergency":
            # Try to bump a Medium/Low admitted patient
            admitted = st.session_state.patients[
                (st.session_state.patients["Status"] == "Admitted") &
                (st.session_state.patients["Priority"].isin(["Low", "Medium"]))
            ].copy()
            if not admitted.empty:
                # Remove the lowest priority, latest admitted patient
                admitted["PriorityValue"] = admitted["Priority"].map(priority_map)
                admitted = admitted.sort_values(["PriorityValue", "ID"], ascending=[False, False])
                to_bump = admitted.iloc[0]
                idx_bump = to_bump.name
                bed_to_free = to_bump["Assigned Bed"]
                # Move the bumped patient back to waiting
                st.session_state.patients.at[idx_bump, "Status"] = "Waiting"
                st.session_state.patients.at[idx_bump, "Assigned Bed"] = None
                # Assign this bed to the emergency patient
                st.session_state.patients.at[idx, "Status"] = "Admitted"
                st.session_state.patients.at[idx, "Assigned Bed"] = bed_to_free
                st.session_state.patients.at[idx, "Admit Date"] = str(date.today())
                st.session_state.beds.loc[st.session_state.beds["Bed ID"] == bed_to_free, "Status"] = "Occupied"
                st.info(f"Bumped patient {to_bump['Name']} ({to_bump['Priority']}) for emergency admission.")
            # If no one to bump, emergency remains waiting

def main():
    st.title("🏥 Hospital Queuing and Patient Management System")

    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        with st.sidebar:
            st.header("Login")
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.button("Login"):
                if authenticate_user(username, password):
                    st.session_state.authenticated = True
                    st.success(f"Welcome, {st.session_state.role}!")
                    st.rerun()
                else:
                    st.error("Invalid credentials")
        return

    app_menu()

def app_menu():
    st.sidebar.header(f"Logged in as: {st.session_state.role}")
    menu_options = ["Queue Management", "Bed Availability", "Patient Admission", "Discharge Patient"]
    if st.session_state.role == "Admin":
        menu_options.append("Admin Dashboard")
    menu = st.sidebar.selectbox("Menu", menu_options)
    if menu == "Queue Management":
        queue_management()
    elif menu == "Bed Availability":
        bed_availability()
    elif menu == "Patient Admission":
        patient_admission()
    elif menu == "Discharge Patient":
        discharge_patient()
    elif menu == "Admin Dashboard" and st.session_state.role == "Admin":
        admin_dashboard()

def queue_management():
    assign_beds_to_waiting_patients()
    st.header("🔄 Current Queue Status")

    # Only show waiting and admitted patients
    waiting = st.session_state.patients[st.session_state.patients["Status"] == "Waiting"]
    admitted = st.session_state.patients[st.session_state.patients["Status"] == "Admitted"]

    st.subheader("🟡 Waiting Patients")
    st.dataframe(waiting, use_container_width=True)

    st.subheader("🟢 Admitted Patients")
    st.dataframe(admitted, use_container_width=True)

    st.markdown("---")
    st.subheader("Today's Patient Summary")
    today = str(date.today())
    today_patients = st.session_state.patients[st.session_state.patients["Admit Date"] == today]
    st.write(f"**Total Patients Today:** {len(today_patients)}")
    st.write(f"**Admitted Today:** {len(today_patients[today_patients['Status'] == 'Admitted'])}")
    st.write(f"**Waiting Today:** {len(today_patients[today_patients['Status'] == 'Waiting'])}")
    st.write(f"**Discharged Today:** {len(today_patients[today_patients['Status'] == 'Discharged'])}")

    if st.button("🔄 Refresh Queue"):
        st.rerun()
    with st.expander("📝 Add New Patient to Queue"):
        with st.form("Add Patient Form"):
            name = st.text_input("Patient Name", key="queue_name")
            age = st.number_input("Age", min_value=0, max_value=120, key="queue_age")
            medical_history = st.text_area("Medical History", key="queue_history")
            priority = st.selectbox("Priority", ["Low", "Medium", "Emergency"], key="queue_priority")
            if st.form_submit_button("➕ Add to Queue"):
                if name.strip() == "":
                    st.error("Please enter patient name")
                else:
                    new_patient = pd.DataFrame({
                        "ID": [len(st.session_state.patients) + 1],
                        "Name": [name],
                        "Age": [age],
                        "Medical History": [medical_history],
                        "Status": ["Waiting"],
                        "Assigned Bed": [None],
                        "Priority": [priority],
                        "Admit Date": [str(date.today())]
                    })
                    st.session_state.patients = pd.concat(
                        [st.session_state.patients, new_patient], 
                        ignore_index=True
                    )
                    st.success(f"Patient {name} added to queue!")
                    st.rerun()

def bed_availability():
    st.header("🛏️ Bed Availability Status")
    available_beds = st.session_state.beds[st.session_state.beds["Status"] == "Available"].shape[0]
    occupied_beds = st.session_state.beds[st.session_state.beds["Status"] == "Occupied"].shape[0]
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Available Beds", available_beds)
    with col2:
        st.metric("Occupied Beds", occupied_beds)
    st.dataframe(st.session_state.beds, use_container_width=True)
    with st.expander("⚙️ Update Bed Status"):
        with st.form("Update Bed Form"):
            bed_id = st.selectbox("Select Bed", st.session_state.beds["Bed ID"])
            status = st.selectbox("Select Status", ["Available", "Occupied"])
            if st.form_submit_button("Update Status"):
                st.session_state.beds.loc[st.session_state.beds["Bed ID"] == bed_id, "Status"] = status
                if status == "Available":
                    st.session_state.patients.loc[
                        st.session_state.patients["Assigned Bed"] == bed_id,
                        ["Status", "Assigned Bed"]
                    ] = ["Discharged", None]
                st.success(f"Bed {bed_id} status updated to {status}!")
                st.rerun()

def patient_admission():
    st.header("📋 Patient Admission")
    with st.form("Admission Form"):
        st.subheader("Patient Details")
        name = st.text_input("Full Name")
        age = st.number_input("Age", min_value=0, max_value=120)
        medical_history = st.text_area("Medical History")
        priority = st.selectbox("Priority", ["Low", "Medium", "Emergency"])
        if st.form_submit_button("Admit Patient"):
            if len(name.strip()) < 2:
                st.error("Please enter a valid name")
            else:
                new_patient = pd.DataFrame({
                    "ID": [len(st.session_state.patients) + 1],
                    "Name": [name],
                    "Age": [age],
                    "Medical History": [medical_history],
                    "Status": ["Waiting"],
                    "Assigned Bed": [None],
                    "Priority": [priority],
                    "Admit Date": [str(date.today())]
                })
                st.session_state.patients = pd.concat(
                    [st.session_state.patients, new_patient],
                    ignore_index=True
                )
                st.success(f"Patient {name} added to queue!")
                st.rerun()

def discharge_patient():
    st.header("🏥 Discharge Patient")
    admitted = st.session_state.patients[st.session_state.patients["Status"] == "Admitted"]
    if admitted.empty:
        st.info("No admitted patients to discharge.")
        return
    with st.form("Discharge Form"):
        patient_names = admitted["Name"] + " (Bed: " + admitted["Assigned Bed"].astype(str) + ")"
        selected = st.selectbox("Select Patient to Discharge", patient_names)
        if st.form_submit_button("Discharge"):
            idx = admitted[patient_names == selected].index[0]
            bed_id = admitted.loc[idx, "Assigned Bed"]
            st.session_state.patients.at[idx, "Status"] = "Discharged"
            st.session_state.patients.at[idx, "Assigned Bed"] = None
            st.session_state.beds.loc[st.session_state.beds["Bed ID"] == bed_id, "Status"] = "Available"
            st.success(f"Patient {admitted.loc[idx, 'Name']} discharged from {bed_id}.")
            st.rerun()

def admin_dashboard():
    assign_beds_to_waiting_patients()
    st.header("📊 Admin Dashboard")
    st.subheader("Patient Statistics")
    total_patients = len(st.session_state.patients)
    waiting_patients = len(st.session_state.patients[st.session_state.patients["Status"] == "Waiting"])
    admitted_patients = len(st.session_state.patients[st.session_state.patients["Status"] == "Admitted"])
    discharged_patients = len(st.session_state.patients[st.session_state.patients["Status"] == "Discharged"])
    cols = st.columns(4)
    cols[0].metric("Total Patients", total_patients)
    cols[1].metric("Waiting", waiting_patients)
    cols[2].metric("Admitted", admitted_patients)
    cols[3].metric("Discharged", discharged_patients)
    st.subheader("Patient Age Distribution")
    if not st.session_state.patients.empty:
        st.bar_chart(st.session_state.patients["Age"].value_counts())
    else:
        st.info("No patient data available")
    if st.button("🔄 Reset System Data (Demo Only)"):
        st.session_state.patients = pd.DataFrame(
            columns=["ID", "Name", "Age", "Medical History", "Status", "Assigned Bed", "Priority", "Admit Date"]
        )
        st.session_state.beds = pd.DataFrame(columns=["Bed ID", "Status"])
        for i in range(1, 21):
            new_bed = pd.DataFrame({"Bed ID": [f"Bed {i}"], "Status": ["Available"]})
            st.session_state.beds = pd.concat([st.session_state.beds, new_bed], ignore_index=True)
        st.success("System data reset complete!")
        st.rerun()

if __name__ == "__main__":
    main()