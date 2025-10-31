from streamlit import st
from src.schedule import schedule_modules
from src.ui import display_input_form, display_results

def main():
    st.title("Module Scheduling Application")
    st.write("This application schedules modules based on adsorption, desorption, and cooling durations.")

    # Display input form for user to enter scheduling parameters
    ads, des, cool, fans, fixed_makespan, cycles_mode = display_input_form()

    if st.button("Schedule"):
        # Call the scheduling function and get results
        plotted_intervals, per_module_done, total_done = schedule_modules(
            ads, des, cool, fans, cycles_mode=cycles_mode, fixed_makespan=fixed_makespan
        )

        # Display the results
        display_results(plotted_intervals, per_module_done, total_done)

if __name__ == "__main__":
    main()