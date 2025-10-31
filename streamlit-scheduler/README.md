# Streamlit Scheduler

This project is a Streamlit application designed to schedule modules based on their adsorption, desorption, and cooling durations. It utilizes optimization techniques to maximize the efficiency of the scheduling process.

## Project Structure

```
streamlit-scheduler
├── src
│   ├── app.py          # Main entry point for the Streamlit application
│   ├── schedule.py     # Contains scheduling logic and functions
│   ├── ui.py           # Defines user interface components
│   └── helpers.py      # Utility functions for data processing and validation
├── requirements.txt     # Lists Python dependencies for the project
├── .streamlit
│   └── config.toml     # Configuration settings for the Streamlit app
├── .gitignore           # Specifies files to be ignored by Git
└── README.md            # Documentation for the project
```

## Installation

To set up the project, follow these steps:

1. Clone the repository:
   ```
   git clone <repository-url>
   cd streamlit-scheduler
   ```

2. Create a virtual environment (optional but recommended):
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

To run the Streamlit application, execute the following command in your terminal:

```
streamlit run src/app.py
```

This will start the Streamlit server and open the application in your default web browser.

## Features

- Input forms for specifying adsorption, desorption, and cooling durations.
- Visualization of the scheduling results in a Gantt chart format.
- Optimization of module scheduling to maximize completed cycles within a specified time horizon.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any enhancements or bug fixes.

## License

This project is licensed under the MIT License. See the LICENSE file for more details.