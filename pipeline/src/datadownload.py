import pandas as pd
import requests
import sys
import os
from io import StringIO
from pathlib import Path
import re
import duckdb
import numpy as np

# Get the current working directory
current_working_directory = os.getcwd()

# Convert the current working directory to a Path object
script_dir = Path(current_working_directory)

global model_dict
global transmission_dict
global fuel_dict
global stats_can_dict
global month_dic

model_dict = {
    "4wd/4X4": "Four-wheel drive",
    "awd": "All-wheel drive",
    "ffv": "Flexible-fuel vehicle",
    "swb": "Short wheelbase",
    "lwb": "Long wheelbase",
    "ewb": "Extended wheelbase",
    "cng": "Compressed natural gas",
    "ngv": "Natural gas vehicle",
    "#": "High output engine that \
            provides more power than the standard \
            engine of the same size",
}

transmission_dict = {
    "A": "automatic",
    "AM": "automated manual",
    "AS": "automatic with select Shift",
    "AV": "continuously variable",
    "M": "manual",
    "1 – 10": "Number of gears",
}

fuel_dict = {
    "X": "regular gasoline",
    "Z": "premium gasoline",
    "D": "diesel",
    "E": "ethanol (E85)",
    "N": "natural gas",
    "B": "electricity",
}

hybrid_fuel_dict = {
    "B/X": "electricity & regular gasoline",
    "B/Z": "electricity & premium gasoline",
    "B/Z*": "electricity & premium gasoline",
    "B/X*": "electricity & regular gasoline",
    "B": "electricity",
}

stats_can_dict = {
    "new_motor_vehicle_reg": "https://www150.statcan.gc.ca/n1/tbl/csv/20100024-eng.zip",  # noqa E501
    "near_zero_vehicle_registrations": "https://www150.statcan.gc.ca/n1/tbl/csv/20100025-eng.zip",  # noqa E501
    "fuel_sold_motor_vehicles": "https://www150.statcan.gc.ca/n1/tbl/csv/23100066-eng.zip",  # noqa E501
    "vehicle_registrations_type_vehicle": "https://www150.statcan.gc.ca/n1/tbl/csv/23100067-eng.zip",  # noqa E501
}

month_dic = {
    "jan": "01",
    "feb": "02",
    "mar": "03",
    "apr": "04",
    "may": "05",
    "jun": "06",
    "jul": "07",
    "aug": "08",
    "sep": "09",
    "oct": "10",
    "nov": "11",
    "dec": "12",
}


def fuel_consumption_metadata_extraction() -> pd.DataFrame:
    """
    Extract metadata from fuel consumption data

    Returns
    -------
    final_result : pd.DataFrame
        Dataframe containing metadata from fuel consumption data
    """
    try:
        # Extract data in JSON format from URL
        url_open_canada = "https://open.canada.ca/data/api/action/package_show?id=98f1a129-f628-4ce4-b24d-6f16bf24dd64"  # noqa E501
        json_resp = requests.get(url_open_canada)
        # Check response is successful and application is of type JSON
        if (
            json_resp.status_code == 200
            and "application/json" in json_resp.headers.get("Content-Type", "")
        ):
            # Format data and obtain entries in english
            open_canada_data = json_resp.json()
            data_entries = pd.json_normalize(
                open_canada_data["result"], record_path="resources"
            )
            data_entries["language"] = data_entries["language"].apply(
                lambda col: col[0]
            )
            data_entries_english = data_entries[
                data_entries["language"] == "en"
            ]  # noqa E501
            final_result = data_entries_english[["name", "url"]]
        else:
            print(
                "Error - check the url is still valid \
                https://open.canada.ca/data/api/action/package_show?id=98f1a129-f628-4ce4-b24d-6f16bf24dd64"  # noqa E501
            )
            final_result = pd.DataFrame(columns=["name", "url"])
            sys.exit(1)
        return final_result
    except requests.exceptions.HTTPError as errh:
        print("Http Error:", errh)
    except requests.exceptions.ConnectionError as errc:
        print("Error Connecting:", errc)
    except requests.exceptions.Timeout as errt:
        print("Timeout Error:", errt)
    except requests.exceptions.RequestException as err:
        print("OOps: Something Else", err)


def extract_raw_data(url: str):
    """
    Extract raw data from a URL

    Parameters
    ----------
    url : str
        URL to extract data from

    """
    try:
        # Perform query
        csv_req = requests.get(url)
        # Parse content
        url_content = csv_req

        return url_content
    except requests.exceptions.HTTPError as errh:
        print("Http Error:", errh)
    except requests.exceptions.ConnectionError as errc:
        print("Error Connecting:", errc)
    except requests.exceptions.Timeout as errt:
        print("Timeout Error:", errt)
    except requests.exceptions.RequestException as err:
        print("OOps: Something Else", err)


def rename_fuel_data_columns(df) -> pd.DataFrame:
    """
    This function reads a csv and changes its column names
    to lowercase, removes spaces and replaces them with underscores
    and removes the pound sign from the column names

    This function assumes the original csv file has two headers!!!

    Parameters
    ----------
    folder_path : str
        Path to the folder where the data is saved
    csv_file_name : str
        Name of the csv file to be read

    Returns
    -------
        final_df : pd.DataFrame
    """

    # Data cleaning
    sample_df_col = df.dropna(thresh=1, axis=1).dropna(thresh=1, axis=0)
    sample_df_col.columns = [item.lower() for item in sample_df_col.columns]
    sample_df_no_footer = sample_df_col.dropna(thresh=3, axis=0)

    # Remove Unnamed cols
    cols = sample_df_no_footer.columns
    cleaned_cols = [
        re.sub(r"unnamed: \d*", "fuel consumption", item)
        if "unnamed" in item
        else item  # noqa E501
        for item in cols
    ]

    # Clean row 1 on df
    str_item_cols = [
        str(item) for item in sample_df_no_footer.iloc[0:1,].values[0]
    ]  # noqa E501
    str_non_nan = ["" if item == "nan" else item for item in str_item_cols]

    # Form new columns
    new_cols = []
    for itema, itemb in zip(cleaned_cols, str_non_nan):
        new_cols.append(
            f"{itema}_{itemb}".lower()
            .replace("*", "")
            .replace(" ", "")
            .replace(r"#=highoutputengine", "")
        )

    # Reset column names
    final_df = sample_df_no_footer.iloc[1:,].copy()
    final_df.columns = new_cols

    return final_df


def read_and_clean_df(final_df) -> pd.DataFrame:
    """
    This function reads a csv file and performs data cleaning

    Parameters
    ----------
    folder_path : str
        Path to the folder where the data is saved
    csv_file_name : str
        Name of the csv file to be read

    Returns
    -------
    final_df : pd.DataFrame
        Dataframe containing the cleaned data

    """

    final_df = rename_fuel_data_columns(final_df)

    # Additional data cleaning
    final_df.drop_duplicates(keep="first", inplace=True)

    # Turn make, model.1_, vehicleclass_ into lowercase
    final_df["make_"] = final_df["make_"].str.lower().str.strip()
    final_df["model.1_"] = final_df["model.1_"].str.lower()
    final_df["vehicleclass_"] = final_df["vehicleclass_"].str.lower()

    # Character cleaning for vehicleclass_: replace ":" with "-"
    final_df["vehicleclass_"] = final_df["vehicleclass_"].str.replace(
        ":", " -"
    )  # noqa E501

    # Turn make, model.1_, vehicleclass_ into categorical variables
    final_df["make_"] = final_df["make_"].astype("category")
    final_df["model.1_"] = final_df["model.1_"].astype("category")
    final_df["vehicleclass_"] = final_df["vehicleclass_"].astype("category")

    # Mappings
    final_df = final_df.join(
        final_df["transmission_"]
        .str.split(r"(\d+)", expand=True)
        .drop(columns=[2])
        .rename(columns={0: "transmission_type", 1: "number_of_gears"})
    )
    final_df["transmission_type"] = final_df["transmission_type"].map(
        transmission_dict
    )  # noqa E501

    return final_df


def convert_model_key_words(s, dictionary):
    """
    Add values from footnote
    Parameters
    ----------
    s : pd.Series
        row of dataframe
    dictionary : dict
        one of the dictionaries defined globally.
    """

    group = "unspecified"
    for key in dictionary:
        if key in s:
            group = dictionary[key]
            break
    return group


# +
def concatenate_dataframes(df1, df2, df3):
    """
    Concatenates three dataframes based on different number of columns.

    Parameters
    ----------
    df1 : pd.DataFrame
        First dataframe.
    df2 : pd.DataFrame
        Second dataframe.
    df3 : pd.DataFrame
        Third dataframe.

    Returns
    -------
    pd.DataFrame
        Concatenated dataframe.
    """

    # Get the union of the column names of all three dataframes.
    column_names = set.union(
        set(df1.columns), set(df2.columns), set(df3.columns)
    )  # noqa E501

    # Create a new dataframe with the union of column names.
    df = pd.DataFrame(columns=list(column_names))

    # Concatenate the dataframes along the rows (axis=0).
    df = pd.concat([df, df1], ignore_index=True)
    df = pd.concat([df, df2], ignore_index=True)
    df = pd.concat([df, df3], ignore_index=True)

    # Fill in missing columns with NaN values.
    for column in column_names:
        if column not in df.columns:
            df[column] = np.nan

    return df


def create_table(con, table_name, df_var_name):
    """
    Create a table in DuckDB

    Parameters
    ----------
    con : duckdb.connect
        Connection to DuckDB
    table_name : str
        Name of the table to be created
    df_var_name : str
        Name of the dataframe to be used to create the table
    """
    con.execute(f"DROP TABLE IF EXISTS {table_name}")
    con.execute(
        f"CREATE TABLE {table_name} AS SELECT * FROM {df_var_name}"
    )  # noqa E501


def init_duck_db(duckdb_file_path):
    """
    Initialize DuckDB database and create tables for each dataframe

    Parameters
    ----------
    duckdb_file_path : str
        Path to the DuckDB database file

    """
    con = duckdb.connect(duckdb_file_path)

    # Drop tables if they exist
    create_table(con, "fuel", "fuel_based_df")
    create_table(con, "electric", "electric_df")
    create_table(con, "hybrid", "hybrid_df")
    create_table(con, "all_vehicles", "all_vehicles_df")

    con.close()


if __name__ == "__main__":
    clean_data_DB_path = current_working_directory

    print("Clean data DB path: ", clean_data_DB_path)

    # Master dataframe initialization
    fuel_based_df = []

    # Fuel consumption metadata extraction urls
    data_entries_english = fuel_consumption_metadata_extraction()

    for item in data_entries_english.iterrows():
        name, url = item[1]["name"], item[1]["url"]

        if "Original" in name:
            continue

        # Form file name
        file_name = f'{name.replace(" ","_")}.csv'

        # Extract raw data
        item_based_url = extract_raw_data(url)

        # Read and clean as pandas df
        df = pd.read_csv(StringIO(item_based_url.text), low_memory=False)
        final_df = read_and_clean_df(df)

        # Populate dataframe with information from the footnotes
        if "hybrid" in name:
            # Strip numbers from file_name
            name = re.sub(r"\d+", "", name)
            # Strip parenthesis and - from name
            name = name.replace("(", "").replace(")", "").replace("-", "")
            # Form file name
            file_name = f'{name.replace(" ","_")}.csv'

            final_df.rename(
                columns={
                    "model.1_": "model",
                    "fuel.1_type2": "fuel_type2",
                    "consumption.1_city(l/100km)": "fuelconsumption_city_l_100km",  # noqa E501
                    "motor_(kw)": "motor_kw",
                    "enginesize_(l)": "enginesize_l",
                    "consumption_combinedle/100km": "consumption_combinedle_100km",  # noqa E501
                    "range1_(km)": "range1_km",
                    "recharge_time(h)": "recharge_time_h",
                    "fuelconsumption_city(l/100km)": "fuelconsumption_city_l_100km",  # noqa E501
                    "fuelconsumption_hwy(l/100km)": "fuelconsumption_hwy_l_100km",  # noqa E501
                    "fuelconsumption_comb(l/100km)": "fuelconsumption_comb_l_100km",  # noqa E501
                    "range2_(km)": "range2_km",
                    "co2emissions_(g/km)": "co2emissions_g_km",
                },
                inplace=True,
            )  # noqa E501
            final_df["mapped_fuel_type"] = final_df["fuel_type2"].map(
                fuel_dict
            )  # noqa E501
            final_df["hybrid_fuels"] = final_df["fuel_type1"].map(
                hybrid_fuel_dict
            )  # noqa E501

            final_df["id"] = range(1, len(final_df) + 1)
            final_df["vehicle_type"] = "hybrid"
            hybrid_df = final_df
        elif "electric" in name and "hybrid" not in name:
            # Strip numbers from file_name
            name = re.sub(r"\d+", "", name)
            # Strip parenthesis and - from name
            name = name.replace("(", "").replace(")", "").replace("-", "")
            # Form file name
            file_name = f'{name.replace(" ","_")}.csv'

            final_df.rename(
                columns={
                    "model.1_": "model",
                    "motor_(kw)": "motor_kw",
                    "range_(km)": "range1_km",
                    "recharge_time(h)": "recharge_time_h",
                    "consumption_city(kwh/100km)": "consumption_city_kwh_100km",  # noqa E501
                    "fuelconsumption_city(le/100km)": "fuelconsumption_city_l_100km",  # noqa E501
                    "fuelconsumption_hwy(le/100km)": "fuelconsumption_hwy_l_100km",  # noqa E501
                    "fuelconsumption_hwy(kwh/100km)": "fuelconsumption_hwy_kwh_100km",  # noqa E501
                    "fuelconsumption_comb(kwh/100km)": "fuelconsumption_comb_kwh_100km",  # noqa E501
                    "fuelconsumption_comb(le/100km)": "fuelconsumption_comb_l_100km",  # noqa E501
                    "range_(km)": "range1_km",
                    "co2emissions_(g/km)": "co2emissions_g_km",
                },
                inplace=True,
            )  # noqa E501
            final_df["mapped_fuel_type"] = final_df["fuel_type"].map(
                fuel_dict
            )  # noqa E501
            final_df["id"] = range(1, len(final_df) + 1)
            final_df["vehicle_type"] = "electric"
            electric_df = final_df
        else:
            final_df["mapped_fuel_type"] = final_df["fuel_type"].map(fuel_dict)
            final_df["type_of_wheel_drive"] = final_df["model.1_"].apply(
                lambda x: convert_model_key_words(x, model_dict)
            )
            fuel_based_df.append(final_df)

# Concatenate all fuel-based dataframes
fuel_based_df = pd.concat(fuel_based_df)

fuel_based_df.rename(
    columns={
        "model.1_": "model",
        "enginesize_(l)": "enginesize_l",
        "enginesize_(l)": "enginesize_l",
        "consumption_combinedle/100km": "consumption_combinedle_100km",
        "fuelconsumption_city(l/100km)": "fuelconsumption_city_l_100km",
        "fuelconsumption_hwy(l/100km)": "fuelconsumption_hwy_l_100km",
        "fuelconsumption_comb(l/100km)": "fuelconsumption_comb_l_100km",
        "fuelconsumption_comb(mpg)": "fuelconsumption_comb_mpg",
        "co2emissions_(g/km)": "co2emissions_g_km",
    },
    inplace=True,
)  # noqa E501

# add an id column where each row is a unique id (1, 2, 3, 4, ...)
fuel_based_df["id"] = range(1, len(fuel_based_df) + 1)

# Add a column called vehicle_type
fuel_based_df["vehicle_type"] = "fuel-only"

# Call concatenate_dataframes() function to concatenate all dataframes
all_vehicles_df = concatenate_dataframes(fuel_based_df, hybrid_df, electric_df)

# Creating a new directory for DuckDB tables
database_directory = os.path.join(
    current_working_directory, "data", "database"
)  # noqa E501
Path(database_directory).mkdir(parents=True, exist_ok=True)

# Creating DuckDB file at new directory
duckdb_file_path = os.path.join(database_directory, "car_data.duckdb")
init_duck_db(duckdb_file_path)
