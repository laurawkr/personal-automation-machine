import sys
sys.path.insert(0, '/opt/airflow')
import json
from openai import OpenAI
from jira import JIRA
import os
from fpdf import FPDF
from io import BytesIO



def get_chatgpt_response(user_credentials, user_input):
    print("starting chat and forming prompt")
    # Instantiate the OpenAI client using the instance-based interface
    openai_config = user_credentials.get("openai", {})
    openai_api_key = openai_config.get("api_key")
    if not openai_api_key:
        raise ValueError("OpenAI API key not found in credentials.json")
    client = OpenAI(api_key=openai_api_key)
    """
    Calls the ChatGPT API with a system prompt and the user_input,
    then returns the assistant's reply.
    """
    system_prompt = (
        "You are a helpful personal assistant who is our business lead. Your job is to provide scope and business planning for the company."
        "You should respond one of three ways, asking for more information, requesting a review, or providing providing clear and detailed answers or instructions. "
        "Yopu can ask for more information from '@Laura Whicker' or '@Buzz Lightyear'  "
        "you report to @Laura Whicker the ceo, and ask for reviews when you think the request has been fufilled."
        "The other lead is '@Buzz Lightyear' , ask them for clarification on product or engineering related issues"
        "Always provide one message. Do not split your answer into multiple parts (e.g., '(Continued in the next message)')."
        "You are the superior to '@Jessie Yodelton' and you should ask them to do marketing related tasks"
        "You are the superior to '@Hamm Hogsworth' and you should ask them to do finance and legal related tasks"
        "and provide them clear and concise instructions."
        "When reviewing provided info, make decisions for our next steps forward based on our business plan. if you are unclear anout the next step,"
        "Tag '@Laura Whicker' for input. do this liberally."
        "Tag at the start of every comment, you should always either be giving instructions to your subortinates, giving answers and tagging '@Laura Whicker', or asking for business info from"
        "'@Buzz Lightyear' (business/marketing) or '@Laura Whicker' (technical, priorities )"
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_input }
    ]

    try:
        # Use the instance-based method for chat completions
        response = client.chat.completions.create(
            model="chatgpt-4o-latest",
            messages=messages,
            temperature=0.7  # Adjust for creativity if needed
        )
        # Return the assistant's message content from the first choice
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"An error occurred: {e}"

def process_jira_subtasks(user_credentials):
    """
    Connects to Jira, finds all subtask issues in "To Do" status assigned to the current user,
    and for each one sends a prompt to ChatGPT. The response is saved as a document,
    and the document is attached to the Jira issue as an attachment.
    """
    # Get Jira credentials from the loaded JSON configuration
        # Prepare Jira connection
    jira_config = user_credentials.get("jira", {})
    print(jira_config)
    jira_server = jira_config.get("server")
    print(jira_server)
    jira_user = jira_config.get("user")
    print(jira_user)
    jira_api_token = jira_config.get("api_token")
    if not (jira_server and jira_user and jira_api_token):
        print("Error: Jira credentials must be provided.")
        return

    if not jira_server or not jira_user or not jira_api_token:
        print("Error: Jira credentials (server, user, api_token) must be provided in credentials.json.")
        return

    jira_options = {"server": jira_server}
    try:
        jira_client = JIRA(options=jira_options, basic_auth=(jira_user, jira_api_token))
        print(jira_client)
    except Exception as e:
        print(f"Failed to connect to Jira: {e}")
        return

    # JQL to find subtasks in "To Do" status assigned to the current user.
    jql = "assignee = currentUser() AND status = 'To Do' AND issuetype = task"
    try:
        subtasks = jira_client.search_issues(jql)

    except Exception as e:
        print(f"Failed to search for issues: {e}")
        return

    if not subtasks:
        print("No Jira subtasks in 'To Do' status assigned to the current user.")
        return

    # Process each subtask one at a time
    for subtask in subtasks:
        print(f"\nProcessing subtask: {subtask.key}")

        # Retrieve the issue description
        description = subtask.fields.description or "No description provided."

        # Retrieve comments (if any)
        if hasattr(subtask.fields, "comment") and subtask.fields.comment:
            comments = subtask.fields.comment.comments
        else:
            try:
                comments = jira_client.comments(subtask)
            except Exception as e:
                print(f"Failed to retrieve comments for {subtask.key}: {e}")
                comments = []

        # Build the prompt based on whether comments exist.
        if comments:
            try:
                sorted_comments = sorted(comments, key=lambda c: c.created)
            except AttributeError:
                sorted_comments = sorted(comments, key=lambda c: c.get("created", ""))
            if len(sorted_comments) > 1:
                previous_comments = "\n\n".join([c.body if hasattr(c, "body") else c.get("body", "") for c in sorted_comments[:-1]])
                latest_comment = sorted_comments[-1].body if hasattr(sorted_comments[-1], "body") else sorted_comments[-1].get("body", "")
                prompt = (
                    "The initial requirements are: "
                    f"Ticket Description:\n{description}\n\n"
                    "The most recent request to consider is: "
                    f"Latest Comment (current prompt):\n{latest_comment}"
                )
            else:
                latest_comment = sorted_comments[0].body if hasattr(sorted_comments[0], "body") else sorted_comments[0].get("body", "")
                prompt = (
                    f"Ticket Description:\n{description}\n\n"
                    f"Latest Comment (current prompt):\n{latest_comment}"
                )
        else:
            prompt = f"Ticket Description:\n{description}\n\n"

        # Fetch ChatGPT response once
        print("Sending prompt to ChatGPT...")
        answer = get_chatgpt_response(user_credentials, prompt)
        print(f"Response for {subtask.key}:\n{answer}")

        # Post the ChatGPT response as a Jira comment
        try:
            jira_client.add_comment(subtask.key, f"\n{answer}")
            print(f"Added ChatGPT response as a comment to {subtask.key}")
        except Exception as e:
            print(f"Failed to add comment to {subtask.key}: {e}")

        # Process mentions and assign the ticket if applicable
        process_mentions_and_assign(jira_client, subtask)

def process_mentions_and_assign(jira_client, issue):
    """
    Detects if the most recent comment starts with '@', converts the text into a proper Jira mention,
    and assigns the ticket to the mentioned user.
    """
    comments = jira_client.comments(issue)
    if not comments:
        return

    latest_comment = comments[-1]
    latest_comment_body = latest_comment.body.strip()

    # Check if the comment starts with '@'
    if latest_comment_body.startswith("@"):
        try:
            # Extract the username (assumes username is the first word after '@')
            mention = latest_comment_body.split()[0][1:]  # Remove '@' to get the username

            # Search for the user using GDPR-compliant 'query' parameter
            mention_user = jira_client.search_users(query=mention)
            if mention_user:
                user_account_id = mention_user[0].accountId  # Get the user's account ID

                # Replace the plain text with the proper Jira mention format
                updated_comment_body = latest_comment_body.replace(f"@{mention}", f"[~accountid:{user_account_id}]")
                latest_comment.update(body=updated_comment_body)

                # Assign the ticket to the mentioned user
                issue.update(fields={'assignee': {'accountId': user_account_id}})
                print(f"Assigned {issue.key} to {mention} and updated the comment with a proper mention.")
            else:
                print(f"User '{mention}' not found in Jira.")
        except Exception as e:
            print(f"Error processing mention in {issue.key}: {e}")

def run_for_user(user_name, credentials_json):
    """
    This function will be called from the Airflow DAG.
    It extracts the credentials for the given user from the provided JSON
    and then processes Jira subtasks using those credentials.
    """
    print("getting creds 2")
    if user_name not in credentials_json:
        raise ValueError(f"No credentials found for user: {user_name}")
    user_credentials = credentials_json[user_name]
    print("found creds")
    process_jira_subtasks(user_credentials)