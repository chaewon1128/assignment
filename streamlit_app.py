import streamlit as st
import pandas as pd

# Use st.cache_data for efficient data loading, as recommended by Streamlit
@st.cache_data
def load_data():
    """
    Loads all required dataframes from CSV files.
    Initializes missing dataframes as empty DataFrames to prevent NameError.
    """
    
    # --- 1. Define file paths based on uploaded files ---
    spent_file = "spent.csv"
    ppl_2012_file = "ppl_2012.csv"
    ppl_2014_file = "ppl_2014.csv"
    delivery_file = "delivery.csv"
    pol_file = "combined_pol.csv" # Mapped to 'pol'
    trans_file = "trans.csv"

    # --- 2. Initialize all 9 return variables to ensure no NameError ---
    # We initialize them to empty DataFrames just in case reading fails for any of them.
    spent = ppl_2012 = ppl_2014 = delivery = pol = trans = pd.DataFrame()
    GUS = combined_mobility = combined_delivery = pd.DataFrame()
    
    known_files = {
        'spent': spent_file, 
        'ppl_2012': ppl_2012_file, 
        'ppl_2014': ppl_2014_file, 
        'delivery': delivery_file, 
        'pol': pol_file, 
        'trans': trans_file
    }

    st.info("Attempting to load data...")

    # --- 3. Load the known DataFrames with error handling ---
    for var_name, file_path in known_files.items():
        try:
            # Try reading with common Korean encoding ('euc-kr')
            df = pd.read_csv(file_path, encoding='euc-kr') 
            
            # Dynamically assign the loaded DataFrame to the correct variable name
            globals()[var_name] = df
            st.success(f"✅ Successfully loaded {file_path} into `{var_name}`.")
            
        except FileNotFoundError:
            st.warning(f"⚠️ File not found: {file_path}. The variable `{var_name}` remains an empty DataFrame.")
        except UnicodeDecodeError:
            try:
                # Fallback to standard utf-8 encoding
                df = pd.read_csv(file_path, encoding='utf-8')
                globals()[var_name] = df
                st.success(f"✅ Successfully loaded {file_path} into `{var_name}` (using utf-8).")
            except Exception as e:
                st.error(f"❌ Failed to load {file_path} into `{var_name}`. Details: {e}")
        except Exception as e:
            st.error(f"❌ An unexpected error occurred while loading {file_path}: {e}")

    # --- 4. Define placeholder DataFrames for the 3 missing variables ---
    # These must be defined to prevent the NameError in the return statement.
    if GUS.empty:
        GUS = pd.DataFrame({'Note': ['Data for GUS is missing or failed to load.']})
    if combined_mobility.empty:
        combined_mobility = pd.DataFrame({'Note': ['Data for combined_mobility is missing or failed to load.']})
    if combined_delivery.empty:
        combined_delivery = pd.DataFrame({'Note': ['Data for combined_delivery is missing or failed to load.']})

    # The original return statement requiring 9 variables.
    return spent, ppl_2012, ppl_2014, delivery, pol, trans, GUS, combined_mobility, combined_delivery

# --- Main App Execution ---
st.title("Data Dashboard")

# The call that caused the original error (now fixed as all 9 variables are defined in load_data)
try:
    (spent, ppl_2012, ppl_2014, delivery, pol, trans, GUS, combined_mobility, combined_delivery) = load_data()
    st.header("Loaded DataFrames")
    
    # Displaying the first few rows of a few dataframes to verify successful loading
    st.subheader("Spent Data")
    st.dataframe(spent.head())
    
    st.subheader("Transportation Data (trans)")
    st.dataframe(trans.head())
    
    st.subheader("Placeholder Data (GUS)")
    st.dataframe(GUS.head())

except Exception as e:
    st.error(f"An error occurred in the main application logic after loading data: {e}")
