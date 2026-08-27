import os
import re
import requests
import psycopg2
from dotenv import load_dotenv

load_dotenv()
from langchain_core.tools import tool


@tool
def search_logs(service_name: str) -> str:
    """
    Queries recent application logs to find exceptions and symptoms.
    Returns an aggregated summary of error messages and their occurrence counts
    to provide context without overwhelming the token limit.
    """
    axiom_token = os.getenv("AXIOM_API_TOKEN")
    axiom_dataset = os.getenv("AXIOM_DATASET")

    if not axiom_token or not axiom_dataset:
        return "Axiom API token or dataset is not set in environment variables."

    headers = {
        "Authorization": f"Bearer {axiom_token}",
        "Content-Type": "application/json",
    }

    # Groups by the exact error message to retain crucial context (e.g., lock timeouts)
    query = f"['{axiom_dataset}'] | where _time > ago(15m) and service == '{service_name}' and level == 'ERROR' | summarize occurrences=count() by message"

    try:
        response = requests.post(
            "https://api.axiom.co/v1/datasets/_apl?format=legacy",
            headers=headers,
            json={"apl": query},
        )
        response.raise_for_status()
        data = response.json()

        # Extracting the grouped results from Axiom's response payload
        buckets = data.get("buckets", {}).get("totals", [])

        if not buckets:
            return f"No errors found for {service_name} in the last 15 minutes."

        # Formats the output to balance token optimization with rich context
        formatted_summary = "\n".join(
            [
                f"- {b.get('group', {}).get('message', 'Unknown')}: {b.get('occurrences', 0)} occurrences"
                for b in buckets
            ]
        )

        return f"Recent Error Summary for {service_name}:\n{formatted_summary}"

    except Exception as e:
        return f"Error querying logs: {str(e)}"


@tool
def query_database(query: str) -> str:
    """
    Connects to the NeonDB PostGresSQL database and checks for active locks,
    long running queries and also connection exhaustion.
    """
    db_url = os.getenv("NEONDB_URL")

    # Blueprint Compliance: Application-level Regex Validation
    forbidden_pattern = (
        r"\b(DROP|ALTER|UPDATE|INSERT|DELETE|TRUNCATE|GRANT|REVOKE|REPLACE)\b"
    )

    if re.search(forbidden_pattern, query, re.IGNORECASE):
        return "SECURITY ALERT: Query rejected. Destructive SQL commands are strictly prohibited."

    if not db_url:
        return "NeonDB URL is not set in environment variables."

    try:
        conn = psycopg2.connect(db_url, options="-c default_transaction_read_only=on")
        cursor = conn.cursor()

        cursor.execute(query)
        results = cursor.fetchall()
        cursor.close()
        conn.close()

        if not results:
            return "No results found for the executed query."

        return f"Database Observations: {str(results)}"

    except Exception as e:
        return f"Error querying database: {str(e)}"


@tool
def search_git_commits(table_name: str, target_repo: str) -> str:
    """
    Searches the git commit history dynamically.
    Args:
        table_name: The database table implicated in the locks (e.g., 'orders').
        target_repo: The full GitHub repository string to search (e.g., 'JeetNarayanChakraborty/Multi_Agent_Incident_Analyzer_OrderService').
    """

    import time

    github_token = os.getenv("GITHUB_TOKEN")

    if not github_token:
        return "GitHub token is not set in environment variables."

    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3+json",
    }

    # Broaden the search to catch both standard JPA generics and @Table definitions
    entity_guess = "".join(word.capitalize() for word in re.split(r"[_|-]", table_name))

    try:
        # STEP 1: Locate the repository file
        url_search = "https://api.github.com/search/code"
        # Query looks for either the entity name or the raw table name in Java files
        safe_query = f"repo:{target_repo} {entity_guess} OR {table_name} extension:java"

        time.sleep(2)  # Cooling period
        response_search = requests.get(
            url_search, headers=headers, params={"q": safe_query}
        )
        response_search.raise_for_status()
        search_data = response_search.json()

        if search_data.get("total_count", 0) == 0:
            return "No commits found matching the search string."

        file_path = search_data["items"][0]["path"]

        # STEP 2: Retrieve the latest commit that modified this specific file
        url_commits = f"https://api.github.com/repos/{target_repo}/commits"

        time.sleep(2)  # Cooling period
        response_commits = requests.get(
            url_commits, headers=headers, params={"path": file_path, "per_page": 1}
        )
        response_commits.raise_for_status()
        commit_data = response_commits.json()

        if not commit_data:
            return f"Found file in {file_path}, but could not retrieve commit history."

        # Extract the detailed commit metadata
        latest_commit_sha = commit_data[0]["sha"]
        commit_message = commit_data[0]["commit"]["message"]
        author_name = commit_data[0]["commit"]["author"]["name"]

        # STEP 3: Retrieve the pull request associated with the commit
        url_pulls = f"https://api.github.com/repos/{target_repo}/commits/{latest_commit_sha}/pulls"

        time.sleep(2)  # Cooling period
        response_pulls = requests.get(url_pulls, headers=headers)
        response_pulls.raise_for_status()
        pulls_data = response_pulls.json()

        pr_info = "No associated PR found."
        if pulls_data:
            pr_info = f"Introduced via PR #{pulls_data[0]['number']}."

        return (
            f"Found Spring Data Repository in: {file_path}.\n"
            f"Latest Modification: Commit {latest_commit_sha[:7]} by {author_name}.\n"
            f"Commit Message: '{commit_message}'.\n"
            f"{pr_info}"
        )

    except Exception as e:
        return f"Error searching git commits: {str(e)}"


@tool
def dispatch_incident_report(title: str, markdown_body: str) -> str:
    """
    Publishes the final Root Cause Analysis (RCA) and immediate mitigation steps
    to a Github Issue to alert the engineering team.
    Call this STRICTLY and ONLY when the investigation is complete.
    """

    github_token = os.getenv("GITHUB_TOKEN")
    repo = os.getenv("GITHUB_REPO")

    if not github_token or not repo:
        return "GitHub token or repository is not set in environment variables."

    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3+json",
    }

    payload = {
        "title": title,
        "body": markdown_body,
        "labels": ["incident", "automated-triage"],
    }

    try:
        url = f"https://api.github.com/repos/{repo}/issues"
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()

        return f"Successfully created GitHub Issue: {response.json().get('html_url')}"

    except Exception as e:
        return f"Error creating GitHub issue: {str(e)}"
