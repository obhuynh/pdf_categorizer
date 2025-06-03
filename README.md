# PDF Scorer & AI Categorizer

This application reads text from multiple PDF files, uses an AI service (via OpenRouter) to categorize the content based on your instructions, calculates a simple relevance score for each category, and saves the results into a single, structured CSV file.

## Features

-   Processes an entire folder of PDF files at once.
-   Uses AI to intelligently categorize text based on user-defined rules.
-   Removes boilerplate/disclaimer text using regular expressions.
-   Calculates a simple keyword count score for each categorized snippet.
-   Outputs all data into a clean, easy-to-use CSV file.
-   Modern, cross-platform GUI that works on both Windows and macOS.

## Folder Structure

Your project folder should look like this:

```
pdf_categorizer/
├── pdf.py
├── requirements.txt
└── keys.txt
```

## Setup and Installation

Follow these steps to get the application running on your computer.

### Prerequisites

You must have Python 3 installed on your system. You can download it from [python.org](https://www.python.org/downloads/).

---

### Step-by-Step Instructions

1.  **Prepare Your Files**
    * Create a folder on your computer named `pdf_categorizer`.
    * Place the `pdf.py`, `requirements.txt`, and `keys.txt` files inside this folder.

2.  **Add Your API Key**
    * Open the `keys.txt` file.
    * Paste your **OpenRouter API key** into this file.
    * Save and close the file. Make sure there are no extra spaces or blank lines.

3.  **Install Required Libraries**
    * You now need to open a command line interface to install the Python libraries.

    <details>
    <summary><b>For Windows Users</b></summary>

    1.  Open the **Command Prompt** or **PowerShell**. You can find it in the Start Menu.
    2.  Navigate to your project folder using the `cd` command. For example, if your folder is on your Desktop, you would type:
        ```sh
        cd Desktop\pdf_categorizer
        ```
    3.  Install the requirements by running:
        ```sh
        pip install -r requirements.txt
        ```
    </details>

    <details>
    <summary><b>For macOS Users</b></summary>
    
    1.  Open the **Terminal** app. You can find it in `Applications/Utilities`.
    2.  Navigate to your project folder using the `cd` command. For example, if your folder is on your Desktop, you would type:
        ```sh
        cd Desktop/pdf_categorizer
        ```
    3.  Install the requirements by running:
        ```sh
        pip3 install -r requirements.txt
        ```
    </details>

## Running the Application

Once the setup is complete, you can run the application from your terminal/command prompt while you are inside your project folder.

-   **On Windows:**
    ```sh
    python pdf.py
    ```
-   **On macOS:**
    ```sh
    python3 pdf.py
    ```

## How to Use the Application

1.  The application window will appear. Your OpenRouter API key should be loaded automatically.
2.  In the **"PDFs Folder"** field, click "Browse" and select the folder containing the PDF files you want to process.
3.  In the **"Output CSV File"** field, click "Browse" and choose a name and location to save your final `.csv` results file.
4.  Customize the two main text boxes using the guides below.
5.  Click the big **"PROCESS PDFs, SCORE & CREATE CSV"** button to start.
6.  Monitor the progress in the "Processing Status" log at the bottom.
7.  When finished, a "Success" message will appear, and your CSV file will be ready.

### Understanding the AI Instructions

#### The Main Idea
Think of the AI as a new assistant who is very smart but follows instructions *exactly* as you write them. Your job is to give this assistant a clear "filing guide" so it knows what topics to look for in your PDFs and what to name the categories for those topics.

#### The Most Important Rule
The `#` symbol is a special command that tells the assistant: **"Create a new category with the following name."**
For example, `#Earnings` creates a category named "Earnings".

#### Step-by-Step Guide
1.  **Step 1: Choose Your Topics**
    Before you write anything, decide what key subjects you want to find in your documents. For example: `Company A`, `Company B`, `Market News`.

2.  **Step 2: Create Your Category Headings**
    For each topic, write a new line in the box that starts with `#` followed by the topic name. Keep the name simple and to one word if possible.
    * `#CompanyA`
    * `#CompanyB`
    * `#MarketNews`

3.  **Step 3: (Optional) Add a Simple Description**
    To help the AI do a better job, it's a good idea to write a simple sentence under each heading explaining what to look for. The AI uses this as a hint.

4.  **Step 4: Create a "Catch-All" Category**
    It's highly recommended to include a general category at the end, like `#Other` or `#Misc`, to catch any important information that doesn't fit into your main topics.

---

### Understanding the Disclaimer Removal Patterns

#### The Main Idea
This tool is a "Cleaner" that runs *before* your document is sent to the AI. Its only job is to find and delete repeating, unwanted "junk text." Use this to automatically remove things like page numbers, copyright notices, or legal warnings.

If your PDFs are already clean, you can leave this box completely empty.

#### How It Works
You provide a list of "find and delete" rules. Each rule goes on its own separate line.

#### Common Patterns You Can Use
Here are some ready-to-use patterns for common cases.

* **To Remove an Exact, Unchanging Phrase:**
    * **Rule:** Just type the exact text.
    * **Example:** To remove "For internal review only.", add this line to the box:
        ```
        For internal review only.
        ```

* **To Remove Text with Changing Numbers:**
    * **Rule:** Use the special code `\d+` which means "any number".
    * **Example:** To remove page numbers like "Page 5 of 21", add this line:
        ```
        Page \d+ of \d+
        ```

* **To Remove Text that Spans Across Lines:**
    * **Rule:** Use the special code `.*?` which means "any character, any number of times, until the next part of the rule is met".
    * **Example:** To remove a full copyright block, you could add this line:
        ```
        Copyright ©.*?All rights reserved.
        ```