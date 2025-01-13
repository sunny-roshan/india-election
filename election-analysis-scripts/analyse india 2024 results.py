# In this file: load scraped 2024 election results, create plots of party- and alliance-wise vote shares

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

# Set path
pwd
os.chdir('/Users/sunny/Library/CloudStorage/OneDrive-Personal/Documents/Python/Electoral maps project')

# Load scraped election results data
results = pd.read_csv("election_results.csv")
results.describe()  # 9445 rows

# Basic cleaning of strings
cols_to_edit = ['Candidate', 'Constituency', 'Party']
for i in cols_to_edit:
    results[i] = results[i].str.strip().str.upper()

# Separate the Constituency column into Constituency name, Reservation status, and State name; extract Constituency code and verify that it matches Constituency number
pattern = r"(?P<constituency_code>\d+) - (?P<constituency_name>[^(]+)(?:\((?P<reservation_status>ST|SC)\))? \((?P<state>.+)\)"  # regex

# Update the original DataFrame with new columns
results[['Constituency Code', 'Constituency Name', 'Reservation Status', 'State']] = results['Constituency'].str.extract(pattern)
for col in ['Constituency Name', 'State']:
    results[col] = results[col].str.strip()

# verify that constituency code it matches Constituency number (both are from ECI web scraping, but appear on different parts of the webpage)
results['Constituency Code'] = results['Constituency Code'].astype(int)
assert (results['Constituency Code'] == results['Constituency Number']).all()  # True, can drop one of the cols

# Res status is hardly populated in ECI website data. Only 5 are labelled. Drop column later.
results['Constituency Name'][results['Reservation Status'].notna()].value_counts(dropna=False)

# Reshape to get Total votes rows as a column, to verify vote shares. Before doing so, need to convert votes data to numeric
vars_to_num = ['EVM Votes', 'Postal Votes', 'Total Votes', '% of Votes']
for col in vars_to_num:
    results[col] = results[col].replace("-", np.nan)
    results[col] = results[col].astype(float)
    print(results[col].dtype)

# Replace NaN with 0 and convert to int
results[['EVM Votes', 'Postal Votes', 'Total Votes']] = results[['EVM Votes', 'Postal Votes', 'Total Votes']].fillna(0).astype(int)  #

# Verify total
assert (results["EVM Votes"] + results["Postal Votes"] == results["Total Votes"]).all() # Correct sum

# Now create Total Votes Cast column
# Step 1: Extract total votes cast for each constituency. Filter rows where 'Candidate Name' is 'Total' and create a mapping of Constituency to Total Votes
total_votes_mapping = results[results['Candidate'] == 'TOTAL'].set_index('Constituency')['Total Votes']

# Step 2: Map the total votes to the main DataFrame
results['Total Votes Cast'] = results['Constituency'].map(total_votes_mapping)

# Step 3: Calculate vote share for each candidate
results['Vote Share (%)'] = (results['Total Votes'] / results['Total Votes Cast']) * 100

# Verify total votes column - yes, correct
assert (results[results['Candidate'] == 'TOTAL']['Total Votes Cast'] == results[results['Candidate'] == 'TOTAL']['Total Votes']).all(), "Mismatch in total votes"

# After verifying, drop Total rows:
results = results[results['Candidate'] != 'TOTAL'].reset_index(drop=True)

# Compare official and calculated vote shares
results['vote_share_rounded'] = round(results['Vote Share (%)'], 2)
results['vote_share_diff'] = results['vote_share_rounded'] - results['% of Votes']
results['vote_share_diff'].value_counts(dropna=False)  # All 0. great. One NaN is Surat - no share - uncontested

# remove unnecessary cols
columns_to_drop = ['EVM Votes', 'Postal Votes', 'Constituency Code', 'Constituency', 
                   'Reservation Status', 'S.N.', '% of Votes', 'State Code', 
                   'Constituency Number', 'vote_share_rounded', 'vote_share_diff'] 
results = results.drop(columns=[col for col in columns_to_drop if col in results.columns])
results.rename(columns={'Constituency Name' : 'Constituency'}, inplace=True)


# Next, load map shapefile data
# NB. Parliamentary constituency boundaries are unchanged between 2019 and 2024 - except for Assam
# Still using 2019 boundary map as 2024 map is not publicly available yet

districts = gpd.read_file("maps-master/parliamentary-constituencies/india_pc_2019.shp")

# Replicate 2019 cleaning of columns
districts = districts.drop(["ST_CODE", "PC_CODE"], axis=1)
districts.rename(columns = {'ST_NAME' : "State", 
                            'PC_NAME' : "Constituency", 
                            'Res' : "Reserved status"}, inplace=True)

districts = districts.sort_values(by = ["State", "Constituency"], ascending=True, ignore_index=True)

# Correct Jalaun Reserved status (NB different seats might be reserved in 2024 compared to 2019. Need to confirm.)
districts.loc[districts["Constituency"] == "JALAUN (SC)", "Reserved status"] = "SC"
districts['Reserved status'] = districts['Reserved status'].replace({'GEN' : 'General'})

# For simplicity and merge-friendliness, remove 'SC' and 'ST' tags from constituency names
districts["Constituency"] = districts["Constituency"].str.replace(r"\(.*", "", regex=True).str.strip()

# A bit of cleaning of string formatting
for col in ['Constituency', 'State']:
    districts[col] = districts[col].str.strip().str.upper()


# Next, check and clean state and constituency names in the Results and Map datasets so that they merge
# States
districts["State"].unique()
results["State"].unique()

# Create mapping to align mis-matched state names
results_corrected_state_names = {'ANDAMAN & NICOBAR ISLANDS' : 'ANDAMAN AND NICOBAR ISLANDS', 
                                 'DADRA & NAGAR HAVELI AND DAMAN & DIU' : 'DADRA AND NAGAR HAVELI AND DAMAN AND DIU',
                                 'NCT OF DELHI' : 'DELHI'}
districts_corrected_state_names = {'ANDAMAN & NICOBAR' : 'ANDAMAN AND NICOBAR ISLANDS',
                                   'ORISSA' : 'ODISHA',
                                   'DADRA & NAGAR HAVELI' : 'DADRA AND NAGAR HAVELI AND DAMAN AND DIU', 
                                   'DAMAN & DIU' : 'DADRA AND NAGAR HAVELI AND DAMAN AND DIU', 
                                   'JAMMU & KASHMIR' : 'JAMMU AND KASHMIR'}



results["State"] = results["State"].replace(results_corrected_state_names)
districts["State"] = districts["State"].replace(districts_corrected_state_names)

# J&K has been split since 2019 election. Remove Ladakh from J&K, make it a state.
districts.loc[((districts['State'] == 'JAMMU AND KASHMIR') & (districts['Constituency'] == 'LADAKH')), 'State'] = 'LADAKH'

# Constituencies
results["Constituency"].sort_values().unique()

results_corrected_constituency_names = {'ANANTHAPUR' :'ANANTAPUR', 
                                        'ANDAMAN & NICOBAR ISLANDS' : 'ANDAMAN AND NICOBAR ISLANDS',
                                        'BAHARAICH' : 'BAHRAICH', 
                                        'BHANDARA GONDIYA' : 'BHANDARA-GONDIYA',
                                        'DADAR & NAGAR HAVELI' : 'DADRA AND NAGAR HAVELI', 
                                        'GADCHIROLI - CHIMUR' : 'GADCHIROLI-CHIMUR',
                                        'HATKANANGALE' : 'HATKANANGLE', 
                                        'JOYNAGAR' : 'JAYNAGAR', 
                                        #'KALIABOR',  # Assam
                                        'KURNOOLU' : 'KURNOOL', 
                                        #'MANGALDOI',  # Assam
                                        'MUMBAI NORTH CENTRAL' : 'MUMBAI NORTH-CENTRAL', 
                                        'MUMBAI NORTH EAST' : 'MUMBAI NORTH-EAST', 
                                        'MUMBAI NORTH WEST' : 'MUMBAI NORTH-WEST', 
                                        'MUMBAI SOUTH CENTRAL' : 'MUMBAI SOUTH-CENTRAL',
                                        'NARSARAOPET' : 'NARASARAOPET', 
                                        'NORTH-EAST DELHI' : 'NORTH EAST DELHI', 
                                        'NORTH-WEST DELHI' : 'NORTH WEST DELHI', 
                                        #'NOWGONG',  # Assam
                                        'PALAMAU' : 'PALAMU', 
                                        'PATLIPUTRA' : 'PATALIPUTRA', 
                                        'RATNAGIRI- SINDHUDURG' : 'RATNAGIRI-SINDHUDURG',
                                        'SRERAMPUR' : 'SREERAMPUR', 
                                        #'TEZPUR',  # Assam
                                        'THIRUPATHI' : 'TIRUPATI',
                                        'YAVATMAL- WASHIM' : 'YAVATMAL-WASHIM'}

districts_corrected_constituency_names = {'ANANTNAG' : 'ANANTNAG-RAJOURI',
                                          'ANDAMAN & NICOBAR' : 'ANDAMAN AND NICOBAR ISLANDS',
                                          'ARAMBAG' : 'ARAMBAGH',
                                          #'AUTONOMOUS DISTRICT' : ,  # Assam
                                          'DADRA & NAGAR HAVELI' : 'DADRA AND NAGAR HAVELI',
                                          'GAUHATI' : 'GUWAHATI', 
                                          'HARDWAR' : 'HARIDWAR', 
                                          'KARAULI -DHOLPUR' : 'KARAULI-DHOLPUR',
                                          'MUMBAI SOUTH -CENTRAL' : 'MUMBAI SOUTH-CENTRAL',
                                          'PONDICHERRY' : 'PUDUCHERRY',
                                          'RATNAGIRI -SINDHUDURG' : 'RATNAGIRI-SINDHUDURG',
                                          'TONK - SAWAI MADHOPUR' : 'TONK-SAWAI MADHOPUR'}

results["Constituency"] = results["Constituency"].replace(results_corrected_constituency_names)
districts["Constituency"] = districts["Constituency"].replace(districts_corrected_constituency_names)

# Now, merge results with map and check
merged_2024 = pd.merge(districts, results, how="left", on=["State", "Constituency"])
merged_2024[merged_2024['Party'].isna()]['Constituency'].sort_values(ascending=True).unique()  # Only Assam, which has changed


# Create NDA and I.N.D.I.A. alliance groupings
# NDA:
nda_parties_2024 = ['BHARATIYA JANATA PARTY', 'TELUGU DESAM', 
                    'JANATA DAL (UNITED)', 'SHIV SENA', 
                    'PATTALI MAKKAL KATCHI', 'LOK JANSHAKTI PARTY(RAM VILAS)', 
                    'NATIONALIST CONGRESS PARTY', 'BHARATH DHARMA JANA SENA', 
                    'JANATA DAL (SECULAR)', 'TAMIL MAANILA CONGRESS (MOOPANAR)', 
                    'AMMA MAKKAL MUNNETTRA KAZAGAM', 'APNA DAL (SONEYLAL)', 
                    'ASOM GANA PARISHAD', 'JANASENA PARTY', 
                    "NATIONAL PEOPLE'S PARTY", 'RASHTRIYA LOK DAL', 
                    'AJSU PARTY', 'HINDUSTANI AWAM MORCHA (SECULAR)', 
                    'NAGA PEOPLES FRONT', 'NATIONALIST DEMOCRATIC PROGRESSIVE PARTY', 
                    'SIKKIM KRANTIKARI MORCHA', 'RASHTRIYA LOK MORCHA', 
                    'RASHTRIYA SAMAJ PAKSHA', 'SUHELDEV BHARATIYA SAMAJ PARTY', 
                    "UNITED PEOPLE'S PARTY, LIBERAL"]  # Plus independent O. Paneerselvam in TN - Ramanathapuram


# check
india_alliance_parties_2024 = ['INDIAN NATIONAL CONGRESS', 'SAMAJWADI PARTY', 
                               'ALL INDIA TRINAMOOL CONGRESS', 'DRAVIDA MUNNETRA KAZHAGAM', 
                               'SHIV SENA (UDDHAV BALASAHEB THACKERAY)', 'NATIONALIST CONGRESS PARTY – SHARADCHANDRA PAWAR', 
                               'RASHTRIYA JANATA DAL', 'AAM AADMI PARTY', 
                               'JHARKHAND MUKTI MORCHA', 'COMMUNIST PARTY OF INDIA (MARXIST)', 
                               'INDIAN UNION MUSLIM LEAGUE', 'JAMMU & KASHMIR NATIONAL CONFERENCE', 
                               'COMMUNIST PARTY OF INDIA', 'KERALA CONGRESS (M)', 
                               'VIDUTHALAI CHIRUTHAIGAL KATCHI', 'REVOLUTIONARY SOCIALIST PARTY', 
                               'MARUMALARCHI DRAVIDA MUNNETRA KAZHAGAM', 'COMMUNIST PARTY OF INDIA (MARXIST–LENINIST) LIBERATION', 
                               'KERALA CONGRESS', 'PEASANTS AND WORKERS PARTY OF INDIA', 
                               'ALL INDIA FORWARD BLOC', 'JAMMU AND KASHMIR PEOPLES DEMOCRATIC PARTY', 
                               'MANITHANEYA MAKKAL KATCHI', 'KONGUNADU MAKKAL DESIA KATCHI', 
                               'RAIJOR DAL', 'ASSAM JATIYA PARISHAD', 
                               'ALL PARTY HILL LEADERS CONFERENCE', 'ANCHALIK GANA MORCHA', 
                               'MAKKAL NEEDHI MAIAM', 'GOA FORWARD PARTY', 
                               'RASHTRIYA LOKTANTRIK PARTY', 'PURBANCHAL LOK PARISHAD', 
                               'JATIYA DAL ASSAM', 'SAMAJWADI GANARAJYA PARTY', 
                               'INDIAN NATIONAL LEAGUE', 'BHARAT ADIVASI PARTY']


# Now, map results, starting with the BJP
# Create BJP subset of results 
results_2024_bjp = results[results["Party"] == "BHARATIYA JANATA PARTY"].copy()
merged_2024_bjp = pd.merge(districts, results_2024_bjp, on=["State", "Constituency"], how="left")
merged_2024_bjp['Party'].value_counts(dropna=False)  # 436 BJP seats. Should be 441, probably Assam
geo_bjp_2024 = gpd.GeoDataFrame(merged_2024_bjp, geometry='geometry')

# Initial static plot
# Separate the data based on vote share
bjp_candidates = geo_bjp_2024[geo_bjp_2024["Vote Share (%)"] > 0]
nda_candidates = geo_bjp_2024[geo_bjp_2024["Vote Share (%)"].isna()]

# Define the colormap (from lighter to darker orange)
cmap = mcolors.LinearSegmentedColormap.from_list('orange_cmap', ['#FFEB99', '#FF6600'])

# Plot the GeoDataFrame
fig, ax = plt.subplots(1, 1, figsize=(8, 8))

# Plot districts with BJP candidates according to the colour map
bjp_candidates.plot(column="Vote Share (%)", cmap=cmap, linewidth=0.1, edgecolor="gray", ax=ax, legend=True)

# Plot districts with no BJP presence in grey
nda_candidates.plot(color="#D3D3D3", linewidth=0.05, edgecolor="gray", ax=ax)

ax.set_title("Constituency-wise BJP Vote Share in 2024 (%)", fontsize=16)  # Add a title
ax.axis('off')  # Remove axis
plt.show()


# Interactive 2024 map for BJP
# Define the colours and corresponding thresholds
colors = ['#FFEB99', '#FFC266', '#FF9933', '#FF6600']  # Light to dark orange
thresholds = [0, 10, 30, 50, 100]  # Ranges for Vote Share (%)

# Create a StepColormap
colormap = StepColormap(
    colors=colors,
    vmin=0,
    vmax=100,
    index=thresholds,
    caption="BJP Vote Share in 2024"
)

# Initialize the map
m = folium.Map(location=[20.5937, 78.9629], zoom_start=5, tiles=None)

# Add GeoJSON data
geojson = folium.GeoJson(
    geo_bjp_2024.to_json(),
    style_function=lambda feature: {
        'fillColor': (
            '#D3D3D3' if feature['properties']['Vote Share (%)'] in [None, ''] 
            else colormap(float(feature['properties']['Vote Share (%)']))
        ),
        'color': 'black',
        'weight': 0.5,
        'fillOpacity': 0.7,
    },
    tooltip=folium.GeoJsonTooltip(
        fields=['State', 'Constituency', 'Vote Share (%)'],
        aliases=['State:', 'Constituency:', 'Vote share (%):'],
        localize=True
    )
).add_to(m)

# Fit the map to the bounds of the GeoDataFrame
bounds = geo_bjp_2024.total_bounds  # [minx, miny, maxx, maxy]
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
m.save("bjp_vote_share_map_2024.html")
m

# Save BJP results dataset
geo_bjp_2024.to_file("geo_bjp_2024.geojson", driver="GeoJSON")


# Congress maps
# Subset of results
results_2024_congress = results[results["Party"] == "INDIAN NATIONAL CONGRESS"].copy()
merged_2024_congress = districts.merge(results_2024_congress, on=["State", "Constituency"], how="left")
merged_2024_congress['Party'].value_counts(dropna=False)  # 323 INC. Should be 326. Probably Assam
geo_congress_2024 = gpd.GeoDataFrame(merged_2024_congress, geometry='geometry')

# Save Congress results dataset
geo_congress_2024.to_file("geo_congress_2024.geojson", driver="GeoJSON")

# Interactive 2024 Congress map

# Define the colours and corresponding thresholds
colors = ['#cff0fc', '#9cd6f5', '#65b9eb', '#0384fc']  # Light to dark blue
thresholds = [0, 10, 30, 50, 100]  # Ranges for Vote Share (%)

# Create a StepColormap
colormap = StepColormap(
    colors=colors,
    vmin=0,
    vmax=100,
    index=thresholds,
    caption="Congress Vote Share in 2024"
)

# Initialize the map
m = folium.Map(location=[20.5937, 78.9629], zoom_start=5, tiles=None)

# Add GeoJSON data
geojson = folium.GeoJson(
    geo_congress_2024.to_json(),
    style_function=lambda feature: {
        'fillColor': (
            '#D3D3D3' if feature['properties']['Vote Share (%)'] in [None, ''] 
            else colormap(float(feature['properties']['Vote Share (%)']))
        ),
        'color': 'black',
        'weight': 0.5,
        'fillOpacity': 0.7,
    },
    tooltip=folium.GeoJsonTooltip(
        fields=['State', 'Constituency', 'Vote Share (%)'],
        aliases=['State:', 'Constituency:', 'Vote share (%):'],
        localize=True
    )
).add_to(m)

# Fit the map to the bounds of the GeoDataFrame
bounds = geo_congress_2024.total_bounds  # [minx, miny, maxx, maxy]
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
m.save("congress_vote_share_map_2024.html")
m


# NDA map
# Subset of results
nda_results_2024 = results.copy()
nda_results_2024['nda_tag'] = ((nda_results_2024["Party"].isin(nda_parties_2024)) | 
                              ((nda_results_2024["Constituency"] == "RAMANATHAPURAM") & (nda_results_2024["Candidate"] == "PANNEERSELVAM O S/O OTTAKARATHEVAR")))
nda_results_2024 = nda_results_2024[nda_results_2024['nda_tag'] == True]

# Check cases where NDA parties appear to be contesting against each other 
nda_results_2024[nda_results_2024.duplicated(subset=["Constituency", "State"], keep=False)]  # Lots of Rashtriya Samaj Paksha; some National People's Party, some AJSU, one BJP 

# The Rashtriya Samaj Paksha (RSP) contested 18 seats, of which only 1 (in Maharashtra) was part of the NDA
# In the other 17 seats they must have had friendly contests and got <1% vote share
# Drop the non-NDA RSP candidates
nda_results_2024 = nda_results_2024[~((nda_results_2024["Party"] == "RASHTRIYA SAMAJ PAKSHA") & 
                                      (nda_results_2024["State"] != "MAHARASHTRA"))]

# The AJSU contested 3 seats, of which only 1 (Giridih in Jharkhand) was part of NDA. 
# In the other 2 seats they must have had friendly contests and got <0.5% vote share
# Drop the non-NDA AJSU candidates
nda_results_2024 = nda_results_2024[~((nda_results_2024["Party"] == "AJSU PARTY") & 
                                      (nda_results_2024["State"] != "JHARKHAND"))]


# The National People's Party contested 3 seats, of which 2 (both in Meghalaya) were part of NDA
# The other seat is in Mumbai so probably a totally different one-seat party
# Drop NATIONAL PEOPLE'S PARTY from Mumbai North-East
nda_results_2024 = nda_results_2024[~((nda_results_2024["Party"] == "NATIONAL PEOPLE'S PARTY") & 
                                      (nda_results_2024["State"] != "MEGHALAYA"))]

# In Sikkim's lone seat, SKM and BJP are both part of NDA and both contested
# But SKM got ~8x BJP's votes and was the main NDA contestant
# So I'm going to drop BJP Sikkim from NDA dataset
nda_results_2024 = nda_results_2024[~((nda_results_2024["Party"] == "BHARATIYA JANATA PARTY") & 
                                      (nda_results_2024["State"] == "SIKKIM"))]

# Merge results with map
geo_nda_2024 = pd.merge(districts, nda_results_2024, on=["State", "Constituency"], how="left")
geo_nda_2024 = gpd.GeoDataFrame(geo_nda_2024, geometry='geometry')

# Save NDA results + map dataset
geo_nda_2024.to_file("geo_nda_2024.geojson", driver="GeoJSON")

# Basic static map, NDA
# No NDA candidates - Kashmir Valley; plus Assam will be dealt with later
nda_candidates = geo_nda_2024[geo_nda_2024["Vote Share (%)"].notna()]
no_nda_candidates = geo_nda_2024[geo_nda_2024["Vote Share (%)"].isna()]

# Define the colormap (from lighter to darker orange)
cmap = mcolors.LinearSegmentedColormap.from_list('orange_cmap', ['#FFEB99', '#FF6600'])

# Plot the GeoDataFrame
fig, ax = plt.subplots(1, 1, figsize=(8, 8))
nda_candidates.plot(column="Vote Share (%)", cmap=cmap, linewidth=0.1, edgecolor="gray", ax=ax, legend=True)
no_nda_candidates.plot(color="#D3D3D3", linewidth=0.05, edgecolor="gray", ax=ax)

ax.set_title("Constituency-wise NDA Vote Share in 2024 (%)", fontsize=16)  # Add title
ax.axis('off')  # Remove axis
plt.show()


# Interactive 2024 NDA map

# Define the colours and corresponding thresholds
colors = ['#FFEB99', '#FFC266', '#FF9933', '#FF6600']  # Light to dark orange
thresholds = [0, 10, 30, 50, 100]  # Ranges for Vote Share (%)

# Create a StepColormap
colormap = StepColormap(
    colors=colors,
    vmin=0,
    vmax=100,
    index=thresholds,
    caption="NDA Vote Share in 2024"
)

# Initialize the map
m = folium.Map(location=[20.5937, 78.9629], zoom_start=5, tiles=None)

# Add GeoJSON data
geojson = folium.GeoJson(
    geo_nda_2024.to_json(),
    style_function=lambda feature: {
        'fillColor': (
            '#D3D3D3' if feature['properties']['Vote Share (%)'] in [None, ''] 
            else colormap(float(feature['properties']['Vote Share (%)']))
        ),
        'color': 'black',
        'weight': 0.5,
        'fillOpacity': 0.7,
    },
    tooltip=folium.GeoJsonTooltip(
        fields=['State', 'Constituency', 'Vote Share (%)'],
        aliases=['State:', 'Constituency:', 'Vote share (%):'],
        localize=True
    )
).add_to(m)

# Fit the map to the bounds of the GeoDataFrame
bounds = geo_nda_2024.total_bounds  # [minx, miny, maxx, maxy]
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
m.save("nda_vote_share_map_2024.html")
m

# INDIA alliance map
