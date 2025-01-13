# Scrape 2024 Indian parliamentary election results from Election Commission of India's website
# 2019 election: offical statistical reports published on ECI website, no scraping required
# Steps: (1) create list of all valid URLs; (2) loop over all valid URLs and scrape table of results; (3) store results in CSV 

# Load packages
from selenium import webdriver
from selenium.webdriver.common.by import By
import time
import pandas as pd
import os
import io

# Set loc
pwd
os.chdir("/Users/sunny/Library/CloudStorage/OneDrive-Personal/Documents/Python/Electoral maps project")

# First task: listing all valid URLs. Need Selenium due to ECI website's settings. Doesn't seem to be work in headless mode.

# Path to your ChromeDriver
cService = webdriver.ChromeService(executable_path = '/usr/local/bin/chromedriver')

# Initialize Selenium WebDriver
driver = webdriver.Chrome(service = cService)

# List to store valid URLs
valid_urls = []

# Base ECI URL for 2024 election results in states
base_url = "https://results.eci.gov.in/PcResultGenJune2024/ConstituencywiseS"

# Loop through state codes and constituency numbers
for state_code in range(1, 30):  # 28 states -> assuming up to 30 state codes
    for constituency_number in range(1, 81):  # up to 80 constituencies per state
        # Construct the URL
        url = f"{base_url}{state_code:02}{constituency_number}.htm"

        try:
           # Open the URL in the browser
            driver.get(url)
            time.sleep(2)  # Allow time for the page to load

            # Check if the page is valid or throws up an error
            if "Election Commission of India" in driver.page_source:
                print(f"URL exists: {url}")
                valid_urls.append({"state_code": state_code, "constituency_number": constituency_number, "url": url})
            else:
                print(f"Invalid URL found, stopping search for state {state_code}: {url}")
                break  # Exit inner loop if invalid URL is found
        except Exception as e:
            print(f"Error accessing {url}: {e}")
            break  # Exit inner loop on error

# Base URL for 2024 election results in union territories
base_url = "https://results.eci.gov.in/PcResultGenJune2024/ConstituencywiseU"

# Loop through union territory codes and constituency numbers
for ut_code in range(1, 20):  # 9 UTs; assuming up to 20 UT codes
    for constituency_number in range(1, 81):  # Assuming up to 80 constituencies
        # Construct the URL
        url = f"{base_url}{ut_code:02}{constituency_number}.htm"

        try:
            # Open the URL in the browser
            driver.get(url)
            time.sleep(2)  # Allow time for the page to load

            # Check if the page contains valid content
            if "Election Commission of India" in driver.page_source:
                print(f"URL exists: {url}")
                valid_urls.append({"state_code": ut_code, "constituency_number": constituency_number, "url": url})
            else:
                print(f"Invalid URL found, stopping search for UT {ut_code}: {url}")
                break  # Exit inner loop if invalid URL is found
        except Exception as e:
            print(f"Error accessing {url}: {e}")
            break  # Exit inner loop on error


# Close the browser
driver.quit()

# Save valid URLs to a CSV file
valid_urls_df = pd.DataFrame(valid_urls)
valid_urls_df.to_csv("valid_urls.csv", index=False)
print("Valid URLs saved to 'valid_urls.csv'")


# Second task: actually scrape data from all valid URLs. Loop over all valid URLs.

# Path to your ChromeDriver
cService = webdriver.ChromeService(executable_path = '/usr/local/bin/chromedriver')

# Initialize Selenium WebDriver
driver = webdriver.Chrome(service = cService)

# Load the valid URLs from the CSV
valid_urls_df = pd.read_csv("valid_urls.csv")

# We need to extract the right information from the HTML content of the ECI webpage. For this, define the XPaths:
table_xpath = '/html/body/main/div/div[3]'  # XPath for the overall results table
header_xpath = '/html/body/main/div/div[1]/h2/span'  # XPath for the constituency name

# Define a list to store all constituency data
all_data = []

# Loop through all valid URLs
for _, row in valid_urls_df.iterrows():
    url = row['url']
    print(f"Scraping URL: {url}")

    try:
        # Open the URL in the browser
        driver.get(url)
        time.sleep(5)  # Allow time for the page to load

        # Scrape the table
        table_element = driver.find_element(By.XPATH, table_xpath)
        table_html = table_element.get_attribute('outerHTML')
        table_df = pd.read_html(io.StringIO(table_html))[0]

        # Scrape the constituency name
        header_element = driver.find_element(By.XPATH, header_xpath)
        constituency_name = header_element.text  # Extract the text content

        # Add the constituency name to the DataFrame
        table_df['Constituency'] = constituency_name

        # Add additional context from the URL (state and constituency numbers)
        table_df['State Code'] = row['state_code']
        table_df['Constituency Number'] = row['constituency_number']

        # Append the data to the list
        all_data.append(table_df)

    except Exception as e:
        print(f"Error scraping {url}: {e}")

# Close the browser
driver.quit()

# Combine all data into a single DataFrame
full_results_df = pd.concat(all_data, ignore_index=True)

# Save the results to a CSV file
full_results_df.to_csv("election_results.csv", index=False)

print("Scraping complete. Results saved to election_results.csv")
