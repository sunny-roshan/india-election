# In this file: load 2019 general election results from Election Commission of India's full statistical report
# Clean the election data and India constituency map data
# Define political alliances
# Map 2019 results including party and alliance vote shares

# Load packages
import geopandas as gpd
import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.patches import FancyArrow
import xlrd
import folium
from branca.colormap import LinearColormap
from branca.colormap import StepColormap

# Set loc
os.getwd()
base_dir = Path().resolve().parent 

# First load the geographical dataset on India's constituencies from the publicly available shapefile
districts = gpd.read_file("raw map data/parliamentary-constituencies/india_pc_2019.shp")

# Some exploration of the India map file
districts
districts["geometry"].describe()
districts["State"].value_counts()

# Clean the constituencies shapefile dataset
districts = districts.drop(["ST_CODE", "PC_CODE"], axis=1)  # Don't need state and constituency 'codes'
districts.rename(columns = {'ST_NAME' : "State", 
                            'PC_NAME' : "Constituency", 
                            'Res' : "Reserved status"}, inplace=True)
districts = districts.sort_values(by = ["State", "Constituency"], ascending=True, ignore_index=True)  # Sort alphabetically

# Check that the reservation status in the Constituency column is consistent with the "Reservation status" column
districts["Reserved status"] = districts["Reserved status"].replace({"GEN" : "GENERAL"})
sc_districts = districts[districts["Constituency"].str.contains(r"\(SC\)", na=False)].copy()
st_districts = districts[districts["Constituency"].str.contains(r"\(ST\)", na=False)].copy()

# Create a crosstab of 'Constituency' and 'Reserved status'
sc_crosstab_check = pd.crosstab(sc_districts["Constituency"], sc_districts["Reserved status"], margins=True, dropna=False)
st_crosstab_check = pd.crosstab(st_districts["Constituency"], st_districts["Reserved status"], margins=True, dropna=False)

# Check SC (Scheduled Castes) constituencies
print(sc_crosstab_check)  # One has been labelled General - check
sc_districts[sc_districts["Reserved status"] == "GEN"]  # Jalaun in UP. It is reserved: https://jalaun.nic.in/parliamentary-constituency/
districts.loc[districts["Constituency"] == "JALAUN (SC)", "Reserved status"] = "SC"  # Correct Jalaun

# Check ST (Scheduled Tribes) constituencies
print(st_crosstab_check)  # All ST

# SC, ST, General verified. For simplicity and merge-friendliness, remove these from the constituency name
districts["Constituency"] = districts["Constituency"].str.replace(r"\(.*", "", regex=True).str.strip()

# Plot the map, check that it makes sense
fig, ax = plt.subplots(figsize=(15, 15))
districts.boundary.plot(ax=ax, linewidth=0.15)
plt.show()
# Map is fine

# Next step: Load 2019 General Election data.
# 2019 statistical reports have been published, web scraping not required
# Load in ECI election data
election_2019 = pd.read_excel("election_data/ECI Data/33. Constituency Wise Detailed Result.xlsx", 
                              sheet_name="mySheet", 
                              usecols="A:N",
                              skiprows = 2,
                              nrows=8598)

# Clean the data
election_2019.columns = election_2019.columns.str.strip().str.title()  # Reformat the column names
election_2019.rename(columns={"Pc Name" : "Constituency",
                              "State Name" : "State", 
                              "Candidates Name" : "Candidate", 
                              "Category" : "Candidate Category",
                              "Party Name" : "Party",
                              "Total" : "Total Votes",
                              "Over Total Electors In Constituency" : "Overall share", 
                              "Over Total Votes Polled In Constituency" : "Actual share"}, inplace=True)

# Verify that the number of candidates is correct
election_2019_bjp = election_2019[election_2019["Party"] == "BJP"].value_counts(dropna=False)  
# Only 436 contestants, but the BJP contested 437 seats in 2019. One BJP seat is missing

election_2019[(election_2019["State"] == "ANDHRA PRADESH") & (election_2019["Constituency"] == "RAJAMPET")]  # In Rajampet, Andhra Pradesh, the BJP candidate doesn't exist in the ECI data (!). Pappireddi Maheswara Reddy supposedly contested.
# Manually add in Rajampet, AP row as a dictionary
rajampet = {"State": "ANDHRA PRADESH", 
            "Constituency": "RAJAMPET", 
            "Candidate": "Pappireddi Maheswara Reddy".upper(),
            "Candidate Category" : "GENERAL",
            "Party" : "BJP",
            "Total Votes" : 0
           }

# Add the new row to the overall results dataset
election_2019 = pd.concat([election_2019, pd.DataFrame([rajampet])], ignore_index=True)


# Verify that the Total Votes column correctly sums up the General and Postal vote categories
assert (election_2019["General"] + election_2019["Postal"] == election_2019["Total Votes"]).all() # Correct sum

# Calculate total votes polled in each constituency (across all candidates) and move this column
election_2019["Total Votes Cast"] = election_2019.groupby(["State","Constituency"])["Total Votes"].transform("sum")
column_position = election_2019.columns.get_loc("Total Votes") + 1
election_2019.insert(column_position, "Total Votes Cast", election_2019.pop("Total Votes Cast"))

# Manually calculate vote shares, compare them with the figures in the ECI data
election_2019["Vote Share (%)"] = (election_2019["Total Votes"] / election_2019["Total Votes Cast"]) * 100
election_2019["vote_share_diff"] = election_2019["Vote Share (%)"] - election_2019["Actual share"]  # 'Actual share' is from ECI data
abs(election_2019["vote_share_diff"]).describe()  # There seem to be small but widespread differences 
assert (election_2019["vote_share_diff"] >= 0).all()  # True, calculated shares always higher than in ECI data
election_2019[election_2019["vote_share_diff"] <= 0.05]["Candidate"].count()  # 8344 rows have differences <= 0.05pp
election_2019[election_2019["vote_share_diff"] > 0.05]["Constituency"].count()  # 253 rows have differences > 0.05pp!
election_2019.sort_values(by = "vote_share_diff", ascending=False).head(25)
# Not sure why ECI vote shares as wrong. Going to ignore the issue and use my calculated shares.

# Drop unnecessary columns
columns_to_drop = ["General", "Postal", "Sex", "Age", "Party Symbol", "Overall share", "Actual share", "Total Electors", "vote_share_diff"]
election_2019 = election_2019.drop(columns=[col for col in columns_to_drop if col in election_2019.columns])

# Use lambda-apply to convert multiple cols to upper case at once
election_2019[["State", "Constituency"]] = election_2019[["State", "Constituency"]].apply(lambda x: x.str.strip().str.upper())

# Check reservation statuses
election_2019["Candidate Category"].value_counts(dropna = False)
election_2019["Party"][election_2019["Candidate Category"].isna()].value_counts(dropna = False)

# For all NOTA votes, the candidate category column is missing. Fill it in
election_2019["Candidate Category"] = election_2019.groupby(["State", "Constituency"])["Candidate Category"].transform(lambda group: group.ffill()).infer_objects()
# need to edit because NOTA cannot be the first entry in a PC for this to work, but it is on top in Vellore
election_2019[election_2019["Constituency"] == "VELLORE"]  # This is where NOTA is first so candidate category is not updated
# To avoid having NaN valus, label the Vellore NOTA as General
election_2019.loc[((election_2019["Constituency"] == "VELLORE") & 
                   (election_2019["Candidate"] == "NOTA")), ["Candidate Category"]] = "GENERAL"

# Define function to determine overall Reservation status for each constituency (infer from candidate category)
def determine_reservation_status(pc):
    pc["Reservation status"] = None
    if "GENERAL" in pc["Candidate Category"].values:
        pc["Reservation status"] = "GENERAL"
    elif all(pc["Candidate Category"] == "SC"):
        pc["Reservation status"] = "SC"
    elif all(pc["Candidate Category"] == "ST"):
        pc["Reservation status"] = "ST"
    return pc

# Apply the function and check
election_2019 = election_2019.groupby(["State", "Constituency"], group_keys=False).apply(determine_reservation_status, include_groups=True)
election_2019["Reservation status"].value_counts(dropna=False)
pd.crosstab(election_2019["Candidate Category"], election_2019["Reservation status"], dropna=False)
election_2019[election_2019["Reservation status"].isna()]  # Warangal, TG has one pesky ST. It should be an SC constituency

# Fix Warangal Reservation status
election_2019.loc[election_2019["Constituency"] == "WARANGAL", ["Candidate Category", "Reservation status"]] = "SC"
election_2019[election_2019["Constituency"] == "WARANGAL"]  # All SC
election_2019[election_2019["Reservation status"].isna()]  # None

# Now that we have res status column, remove (SC), (ST) labels from constituency names and drop candidate category column
election_2019["Constituency"] = election_2019["Constituency"].str.replace(r"\(.*", "", regex=True).str.strip()
election_2019 = election_2019.drop(["Candidate Category"], axis=1)

# Sort to have winning party at the top and reset index
# We only need parties, not candidate names
# But keep candidates bc at least one independent is in the NDA alliance (in Mandya)
election_2019 = election_2019.sort_values(by = ["State", "Constituency", "Vote Share (%)"], ascending=[True,True,False], ignore_index=True)


# Next, Check that State and Constituency names in the Map and Results datsets match for merge; if they don't, clean
# States
election_2019["State"].unique()
districts["State"].unique()  # Orissa, Delhi, ANDAMAN & NICOBAR need to be edited
# Consituencies:
election_2019["Constituency"].sort_values().unique()

# Edit state names in both datasets so that all names align
# (NB. Dadra - Daman merger happened post-2019 elections)
results_corrected_state_names = {'ANDAMAN & NICOBAR ISLANDS' : 'ANDAMAN AND NICOBAR ISLANDS', 
                                 'NCT OF DELHI' : 'DELHI',
                                 'JAMMU & KASHMIR' : 'JAMMU AND KASHMIR'}

districts_corrected_state_names = {'ANDAMAN & NICOBAR' : 'ANDAMAN AND NICOBAR ISLANDS',
                                   'ORISSA' : 'ODISHA',
                                   'JAMMU & KASHMIR' : 'JAMMU AND KASHMIR'}

results_corrected_constituency_names = {'AHMADNAGAR' : 'AHMEDNAGAR', 
                                        'ANAKAPALLI' : 'ANAKAPALLE',
                                        'ANDAMAN & NICOBAR ISLANDS' : 'ANDAMAN AND NICOBAR ISLANDS',
                                        'ARUKU' : 'ARAKU', 
                                        'BARDHAMAN DURGAPUR' : 'BARDHAMAN-DURGAPUR', 
                                        'BARRACKPORE' : 'BARRACKPUR',
                                        'BHANDARA - GONDIYA' : 'BHANDARA-GONDIYA', 
                                        'COOCH BEHAR' : 'COOCHBEHAR', 
                                        'HARDWAR' : 'HARIDWAR',
                                        'MUMBAI   SOUTH' : 'MUMBAI SOUTH', 
                                        'MUMBAI NORTH CENTRAL' : 'MUMBAI NORTH-CENTRAL',
                                        'MUMBAI NORTH EAST' : 'MUMBAI NORTH-EAST', 
                                        'MUMBAI NORTH WEST' : 'MUMBAI NORTH-WEST', 
                                        'MUMBAI SOUTH CENTRAL' : 'MUMBAI SOUTH-CENTRAL',
                                        'PALAMAU' : 'PALAMU', 
                                        'RATNAGIRI - SINDHUDURG' : 'RATNAGIRI-SINDHUDURG', 
                                        'SARGUJA' : 'SURGUJA',
                                        'SECUNDRABAD' : 'SECUNDERABAD', 
                                        'SRERAMPUR' : 'SREERAMPUR', 
                                        'THIRUVALLUR' : 'TIRUVALLUR'}

districts_corrected_constituency_names = {'ANDAMAN & NICOBAR' : 'ANDAMAN AND NICOBAR ISLANDS',
                                          'ARAMBAG' : 'ARAMBAGH',
                                          'PONDICHERRY' : 'PUDUCHERRY', 
                                          'DADRA & NAGAR HAVELI' : 'DADRA AND NAGAR HAVELI',
                                          'HARDWAR' : 'HARIDWAR',
                                          'KARAULI -DHOLPUR' : 'KARAULI-DHOLPUR',
                                          'MUMBAI SOUTH -CENTRAL' : 'MUMBAI SOUTH-CENTRAL',
                                          'RATNAGIRI -SINDHUDURG' : 'RATNAGIRI-SINDHUDURG',
                                          'TONK - SAWAI MADHOPUR' : 'TONK-SAWAI MADHOPUR'}

election_2019["State"] = election_2019["State"].replace(results_corrected_state_names)
districts["State"] = districts["State"].replace(districts_corrected_state_names)
election_2019["Constituency"] = election_2019["Constituency"].replace(results_corrected_constituency_names)
districts["Constituency"] = districts["Constituency"].replace(districts_corrected_constituency_names)


# Merge 2019 election results with map
merged_2019 = pd.merge(districts, election_2019, on=["State", "Constituency"], how="left")

# Check merge alignment
merged_2019[merged_2019['Party'].isna()]['Constituency'].count()  # 0 mismatches, good

# There are 5 constituencies with mis-matched reservation statuses:
# Akbarpur (UP), Arunachal East, Arunachal West, Ladakh, Nagaland
# Latter 4 definitely General, I think same is true of Akbarpur but not sure
# Need to create a new res status column because neither of the existing ones is perfect
districts["Reservation"] = districts["Reserved status"]

districts.loc[(districts["State"] == "UTTAR PRADESH") & 
    (districts["Constituency"] == "AKBARPUR"), 
    "Reservation"
] = "GENERAL"

merged_2019 = pd.merge(merged_2019, districts[["State", "Constituency", "Reservation"]], 
                       on=["State", "Constituency"], how="left")

merged_2019 = merged_2019.drop(["Reservation status", "Reserved status"], axis=1)



# Now, analysis and mapping of the results
# Starting with the BJP
election_2019_bjp = election_2019[election_2019["Party"] == "BJP"]
merged_2019_bjp = pd.merge(districts, election_2019_bjp, on=["State", "Constituency"], how="left")
merged_2019_bjp["Party"].value_counts(dropna=False)  # 437

# Save BJP results dataset
geo_bjp_2019 = gpd.GeoDataFrame(merged_2019_bjp, geometry='geometry')
geo_bjp_2019.to_file("geo_bjp_2019.geojson", driver="GeoJSON")

# Initial BJP 2019 vote share plot
# Separate the data based on vote share
bjp_candidates = geo_bjp_2019[geo_bjp_2019["Vote Share (%)"].notna()]
nda_candidates = geo_bjp_2019[geo_bjp_2019["Vote Share (%)"].isna()]

# Define the colormap (from lighter to darker orange)
cmap = mcolors.LinearSegmentedColormap.from_list('orange_cmap', ['#FFEB99', '#FF6600'])

fig, ax = plt.subplots(1, 1, figsize=(8, 8))  # Plot the GeoDataFrame

# Plot districts with BJP candidates according to the colourmap
bjp_candidates.plot(column="Vote Share (%)", cmap=cmap, linewidth=0.1, edgecolor="gray", ax=ax, legend=True)

# Plot districts with no BJP presence in grey
nda_candidates.plot(color="#D3D3D3", linewidth=0.05, edgecolor="gray", ax=ax)

ax.set_title("Constituency-wise BJP Vote Share in 2019 (%)", fontsize=16)  # Add title
ax.axis('off')  # Remove axis for better visualization
plt.show()


# Interactive 2019 BJP map
# For the interactive tooltip, make new State and Constituency columns in title case for better formatting, instead of upper case; retain original columns in upper case for merging with 2024 results later
columns_to_title_case = {'Constituency': 'constituency_title', 'State': 'state_title'}
geo_bjp_2019 = geo_bjp_2019.assign(**{new_col: geo_bjp_2019[old_col].str.title() for old_col, new_col in columns_to_title_case.items()})

# Using a discrete step colour map with 4 bins might highlight results better. Define the colours and corresponding thresholds:
colors = ['#FFEB99', '#FFC266', '#FF9933', '#FF6600']  # Light to dark orange
thresholds = [0, 10, 30, 50, 100]  # Ranges for Vote Share (%)

# Create a StepColormap
colormap = StepColormap(
    colors=colors,
    vmin=0,
    vmax=100,
    index=thresholds
)
colormap.caption = "BJP Vote Share in 2019"

# Initialize the map
m = folium.Map(location=[20.5937, 78.9629], zoom_start=5, tiles=None)

# Add GeoJSON data
geojson = folium.GeoJson(
    geo_bjp_2019.to_json(),
    style_function=lambda feature: {
        'fillColor': (
            '#D3D3D3' if feature['properties']['Vote Share (%)'] in [None, ''] 
            else colormap(float(feature['properties']['Vote Share (%)']))
        ),
        'color': 'black',
        'weight': 0.3,
        'fillOpacity': 0.7,
    },
    tooltip=folium.GeoJsonTooltip(
        fields=['state_title', 'constituency_title', 'Vote Share (%)'],
        aliases=['State:', 'Constituency:', 'Vote share (%):'],
        localize=True
    )
).add_to(m)

# Fit the map to the bounds of the GeoDataFrame
bounds = geo_bjp_2019.total_bounds  # [minx, miny, maxx, maxy]
m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])

# Add the colourmap to the map
colormap.add_to(m)

# Inject CSS for a white background
from folium.plugins import FloatImage

css = """
<style>
    .leaflet-container {
        background: #FFFFFF !important;
    }
</style>
"""
folium.Html(css, script=True).add_to(m)

# Save the map
m.save("bjp_vote_share_map_step_colour_2019.html")
#m


# Next, analyse and map Congress party vote shares
congress_2019 = election_2019[election_2019["Party"] == "INC"].copy()  # subset of results data
merged_2019_congress = pd.merge(districts, congress_2019, on=["State", "Constituency"], how="left")  # merge INC results with shapefile
merged_2019_congress["Party"].value_counts(dropna=False)  # 421 - correct

# Save Congress results dataset
geo_congress_2019 = gpd.GeoDataFrame(merged_2019_congress, geometry='geometry')
geo_congress_2019.to_file("geo_congress_2019.geojson", driver="GeoJSON")

# Interactive Congress 2019 plot
# For the interactive tooltip, make new State and Constituency columns in title case for better formatting, instead of upper case; retain original columns in upper case for merging with 2024 results later
columns_to_title_case = {'Constituency': 'constituency_title', 'State': 'state_title'}
geo_congress_2019 = geo_congress_2019.assign(**{new_col: geo_congress_2019[old_col].str.title() for old_col, new_col in columns_to_title_case.items()})

# Define the colors and corresponding thresholds
colors = ['#cff0fc', '#9cd6f5', '#65b9eb', '#0384fc']  # Light to dark blue
thresholds = [0, 10, 30, 50, 100]  # Ranges for Vote Share (%)

# Create a StepColormap
colormap = StepColormap(
    colors=colors,
    vmin=0,
    vmax=100,
    index=thresholds,
    caption="Congress Vote Share in 2019"
)

# Initialise the map
m = folium.Map(location=[20.5937, 78.9629], zoom_start=5, tiles=None)

# Add GeoJSON data
geojson = folium.GeoJson(
    geo_congress_2019.to_json(),
    style_function=lambda feature: {
        'fillColor': (
            '#D3D3D3' if feature['properties']['Vote Share (%)'] in [None, ''] 
            else colormap(float(feature['properties']['Vote Share (%)']))
        ),
        'color': 'black',
        'weight': 0.3,
        'fillOpacity': 0.7,
    },
    tooltip=folium.GeoJsonTooltip(
        fields=['state_title', 'constituency_title', 'Party', 'Vote Share (%)'],
        aliases=['State:', 'Constituency:', 'Party:', 'Vote share (%):'],
        localize=True
    )
).add_to(m)

# Fit the map to the bounds of the GeoDataFrame
bounds = geo_congress_2019.total_bounds  # [minx, miny, maxx, maxy]
m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])

# Add the colormap to the map
colormap.add_to(m)

# Inject CSS for a white background
from folium.plugins import FloatImage

css = """
<style>
    .leaflet-container {
        background: #FFFFFF !important;
    }
</style>
"""
folium.Html(css, script=True).add_to(m)

# Save and display the map
m.save("congress_vote_share_map_step_colour_2019.html")
#m


# Create alliance groupings - NDA and UPA 
# Starting with the NDA
nda_results_2019 = election_2019.copy()  # Create copy of results, which we will subset

# The list of full party names is from Wikipedia. I have manually matched full names to acronyms in the EC election results data
nda_parties_2019 = ["BJP", "SHS", "ADMK", "JD(U)", "SAD", 
                    "PMK", "LJP", "BDJS", "DMDK", "AGP", 
                    "ADAL", "AJSUP", "TMC(M)", "AINRC", 
                    "BOPF", "NDPP", "KEC(M)", "RLTP"]  # NB. "Puthiya Tamilagam" in TN subsumed in ADMK in EC data

# Need to add Mandya where "Sumalatha (Independent candidate)" is NDA
nda_results_2019['nda_tag'] = ((nda_results_2019["Party"].isin(nda_parties_2019)) | 
                              ((nda_results_2019["Constituency"] == "MANDYA") & (nda_results_2019["Candidate"] == "SUMALATHA AMBAREESH")))
nda_results_2019 = nda_results_2019[nda_results_2019['nda_tag'] == True]  # Keep NDA only

# Check whether NDA parties seem to be contesting against each other in the same seat
nda_results_2019[nda_results_2019.duplicated(subset=["Constituency", "State"], keep=False)]  
nda_results_2019["Party"][nda_results_2019.duplicated(subset=["Constituency", "State"], keep=False)].value_counts() # SHS in WB, Bihar, UP, Punjab; JD(U) in UP: these two parties have tiny presences in these states, and their candidates in these states were not in official NDA grouping

# Drop all Shiv Sena rows where they were not in NDA, i.e. all their candidates outside Maharashtra
nda_results_2019 = nda_results_2019[~((nda_results_2019["Party"] == "SHS") & (nda_results_2019["State"] != "MAHARASHTRA"))]

# Drop all JD(U) rows where they were not in NDA, i.e. all their candidates outside Bihar (in UP, J&K, Lakshadweep, MP, Manipur, Punjab)
nda_results_2019 = nda_results_2019[~((nda_results_2019["Party"] == "JD(U)") & (nda_results_2019["State"] != "BIHAR"))]

# Merge NDA results with shapefile
merged_2019_nda = pd.merge(districts, nda_results_2019, on=["State", "Constituency"], how="left")

# Save NDA dataset
geo_nda_2019 = gpd.GeoDataFrame(merged_2019_nda, geometry="geometry")
geo_nda_2019.to_file("geo_nda_2019.geojson", driver="GeoJSON")


# Basic static map of NDA 2019 results:
# Define the colormap (from lighter to darker orange)
cmap = mcolors.LinearSegmentedColormap.from_list('orange_cmap', ['#FFEB99', '#FF6600'])

# Plot the GeoDataFrame
fig, ax = plt.subplots(1, 1, figsize=(8, 8))
geo_nda_2019.plot(column="Vote Share (%)", cmap=cmap, linewidth=0.1, edgecolor="gray", ax=ax, legend=True)

ax.set_title("Constituency-wise NDA Vote Share in 2019 (%)", fontsize=16)  # Add a title
ax.axis('off')  # Remove axis for better visualization
plt.show()  # Show the plot


# Interactive NDA 2019 map
# For the interactive tooltip, make new State and Constituency columns in title case for better formatting, instead of upper case; retain original columns in upper case for merging with 2024 results later
columns_to_title_case = {'Constituency': 'constituency_title', 'State': 'state_title'}
geo_nda_2019 = geo_nda_2019.assign(**{new_col: geo_nda_2019[old_col].str.title() for old_col, new_col in columns_to_title_case.items()})

# Define the colors and corresponding thresholds
colors = ['#FFEB99', '#FFC266', '#FF9933', '#FF6600']  # Light to dark orange
thresholds = [0, 10, 30, 50, 100]  # Ranges for Vote Share (%)

# Create a StepColormap
colormap = StepColormap(
    colors=colors,
    vmin=0,
    vmax=100,
    index=thresholds,
    caption="NDA Vote Share in 2019"
)

# Initialise the map
m = folium.Map(location=[20.5937, 78.9629], zoom_start=5, tiles=None)

# Add GeoJSON data
geojson = folium.GeoJson(
    geo_nda_2019.to_json(),
    style_function=lambda feature: {
        'fillColor': colormap(float(feature['properties']['Vote Share (%)'])),
        'color': 'black',
        'weight': 0.3,
        'fillOpacity': 0.7,
    },
    tooltip=folium.GeoJsonTooltip(
        fields=['state_title', 'constituency_title', "Party", 'Vote Share (%)'],
        aliases=['State:', 'Constituency:', "NDA Party:", 'Vote share (%):'],
        localize=True,
    )
).add_to(m)

# Fit the map to the bounds of the GeoDataFrame
bounds = geo_nda_2019.total_bounds  # [minx, miny, maxx, maxy]
m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])

# Add the colormap to the map
colormap.add_to(m)

# Save and display the map
m.save("nda_vote_share_map_step_colour_2019.html")
#m


# Next, the UPA Alliance
upa_results_2019 = election_2019.copy()  # We will later subset the results

# Define list of UPA parties
# NB: "Marumalarchi Dravida Munnetra Kazhagam", "Kongunadu Makkal Desia Katchi", and "Indhiya Jananayaga Katchi" (1 seat each in TN) all subsumed into DMK in ECI results
# Need to add independent candidates
upa_parties_2019 = ["INC", 
                    "DMK", 
                    "NCP", 
                    "JD(S)", 
                    "BLSP",
                    "JMM",  # Jharkhand Mukti Morcha
                    "CPI",
                    "CPIM",  # Not in Kerala!
                    "HAMS",
                    "VSIP",
                    "IUML",
                    "JANADIP",  # What was SP doing in UP?
                    "VCK",  # One of VCK's two candidates (Viluppuram, TN) seems to have been labelled as DMK
                    "JVM", 
                    "SWP",
                    "BVA",
                    "CPI(ML)(L)",
                    "KEC(M)",
                    "RSP"]


upa_results_2019['upa_tag'] = ((upa_results_2019["Party"].isin(upa_parties_2019)) 
                               #| 
                              #((upa_results_2019["Constituency"] == "") & (upa_results_2019["Candidate"] == "")))

upa_results_2019 = upa_results_2019[upa_results_2019['upa_tag'] == True]

#upa_results_2019["Party"][upa_results_2019.duplicated(subset=["Constituency", "State"], keep=False)].value_counts()


# Indian National Congress	All States and UTs	421	[1][2][3][4][5][6][7][8][9][10][11]
# 2	Dravida Munnetra Kazhagam	Tamil Nadu	20	[2]
# 3	Rashtriya Janata Dal	Bihar, Jharkhand	20	[4]
# 4	Nationalist Congress Party	Maharashtra	19	[3]
# 5	Janata Dal (Secular)	Karnataka	7	[5]
# 6	Rashtriya Lok Samta Party	Bihar	5	[4]
# 7	Jharkhand Mukti Morcha	Jharkhand, Odisha	5	[7]
# 8	Communist Party of India (Marxist)	Odisha, Tamil Nadu	3	[2]
# 9	Hindustani Awam Morcha	Bihar	3	[4]
# 10	Vikassheel Insaan Party	Bihar	3	[4]
# 11	Communist Party of India	Odisha, Tamil Nadu	3	[2]
# 12	Indian Union Muslim League	Kerala, Tamil Nadu	3	[9]
# 13	Jan adhikar party	Uttar Pradesh	3	[6]
# 14	Viduthalai Chiruthaigal Katchi	Tamil Nadu	2	[2]
# 15	Jharkhand Vikas Morcha (Prajatantrik)	Jharkhand	2	[4]
# 16	Swabhimani Paksha	Maharashtra	2	[8]
# 17	Bahujan Vikas Aaghadi	Maharashtra	1	[8]
# 18	Communist Party of India (Marxist–Leninist) Liberation	Bihar	1	[4]
# 19	Kerala Congress (M)	Kerala	1	[9]
# 20	Revolutionary Socialist Party	Kerala	1	[9]
# 21	Kongunadu Makkal Desia Katchi	Tamil Nadu	1	[2]
# 22	Indhiya Jananayaga Katchi	Tamil Nadu	1	[2]
# 23	Marumalarchi Dravida Munnetra Kazhagam	Tamil Nadu	1	[2]
# 24	Jammu & Kashmir National Conference (supported by INC in Srinagar)	Jammu and Kashmir	1	[10]
# 25	Navaneet Kaur (Independent candidate supported by INC in Amravati)	Maharashtra	1	[8]
# 26	Lalnghinglova Hmar (Independent candidate supported by INC in Mizoram)	Mizoram	1	
# 27	Surendra Kumar Gupta (Independent candidate supported by INC in Pilibhit)	Uttar Pradesh	1
