import os
import requests
import psycopg2
from dotenv import load_dotenv
from langchain_core.tools import tool



load_dotenv()


@tool
def search_logs(service_name: str) -> str:
     """ 
     This tool queries the the recent application logs and HTTP 500 errors
     and is used to find exceptions and symptops
     """

     axiom_token = os.getenv("AXIOM_API_TOKEN")
     axiom_dataset = os.getenv("AXIOM_DATASET")

     if not axiom_token or not axiom_dataset:
          return "Axiom API token or dataset is not set in environment variables."

     headers = {
          "Authorization": f"Bearer {axiom_token}",
          "Content-Type": "application/json",
     }

     query = f"['{axiom_dataset}'] | where _time > ago(15m) and service == '{service_name}' and level == 'ERROR' | limit 10"

     try:
          response = requests.post(
               "https://cloud.axiom.co/api/v1/datasets/query",
               headers=headers,
               json={"query": query},
          )
          response.raise_for_status()
          return str(response.json())
     except Exception as e:
          return f"Error querying logs: {str(e)}"


@tool
def query_database(query: str) -> str:
     """
     Connects to the NeonDB PostGresSQL database and checks for active locks,
     long running queries and also connection exhaustion.
     """
     db_url = os.getenv("NEONDB_URL")

     if not db_url:
          return "NeonDB URL is not set in environment variables."

     try:
          conn = psycopg2.connect(db_url, options="-c default_transaction_read_only=on")
          cursor = conn.cursor()
     
          query = """
               Select pid, state, query
               FROM pg_stat_activity
               WHERE state = 'active'
               AND query NOT LIKE '%pg_stat_activity%'
               AND state_change < current_timestamp - interval '5 seconds'; 
               """

          cursor.execute(query)
          results = cursor.fetchall()
          cursor.close()
          conn.close()

          if not results:
               return "No long running queries found."
          
          return f"Active DB Locks found: {str(results)}"
     
     except Exception as e:
          return f"Error querying database: {str(e)}"


@tool
def search_git_commits(search_string: str) -> str:
     """
     This tool searches the git commit history for a given search string (like a SQL query).
     It is used to find recent changes that may have introduced errors or exceptions.
     """

     github_token = os.getenv("GITHUB_TOKEN")
     repo = os.getenv("GITHUB_REPO")

     if not github_token or not repo:
          return "GitHub token or repository is not set in environment variables."

     headers = {
          "Authorization": f"Bearer {github_token}",
          "Accept": "application/vnd.github.v3+json",
     }

     try:
          url = f"https://api.github.com/search/commits?q=repo:{repo}+{search_string}"

          response = requests.get(url, headers=headers)
          response.raise_for_status()
          github_data = response.json()

          if github_data.get("total_count", 0) == 0:
               return "No commits found matching the search string."
          
          commit_info = github_data["items"][0]

          return f"Found in commit: {commit_info['sha']} by {commit_info['commit']['author']['name']}. Message: {commit_info['commit']['message']}"

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
          "labels": ["incident", "automated-triage"]
     }

     try:
          url = f"https://api.github.com/repos/{repo}/issues"
          response = requests.post(url, headers=headers, json=payload)
          response.raise_for_status()

          return f"Successfully created GitHub Issue: {response.json().get('html_url')}"

     except Exception as e:
          return f"Error creating GitHub issue: {str(e)}"