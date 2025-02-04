import os
from openai import OpenAI
from jira import JIRA
from dotenv import load_dotenv

# Load environment variables from a .env file (if you use one)
load_dotenv()

# Instantiate the OpenAI client using the new instance-based interface
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_chatgpt_response(user_input):
    """
    Calls the ChatGPT API with a system prompt and the user_input,
    then returns the assistant's reply using the new instance-based API.
    """
    system_prompt = (
        "You are a helpful personal assistant who helps me manage my business. Provide clear and detailed answers, "
        "and if necessary, ask clarifying questions."
        "Do not provide documents as part of your answer"
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_input}
    ]

    try:
        # Use the instance-based method for chat completions
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.7  # Adjust for creativity if needed
        )
        # Access the assistant's message content from the first choice
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"An error occurred: {e}"

def process_jira_subtasks():
    """
    Connects to Jira, finds all subtask issues in "To Do" status assigned to the current user,
    and for each one sends a prompt (containing the ticket description and attachment details)
    to ChatGPT. It then prints the number of attachments found and posts the ChatGPT response
    as a Jira comment.
    """
    # Get Jira credentials and server from environment variables
    jira_server = os.getenv("JIRA_SERVER")
    jira_user = os.getenv("JIRA_USER")
    jira_api_token = os.getenv("JIRA_API_TOKEN")

    if not jira_server or not jira_user or not jira_api_token:
        print("Error: JIRA_SERVER, JIRA_USER, and JIRA_API_TOKEN must be set in your environment.")
        return

    # Create a Jira client instance
    jira_options = {"server": jira_server}
    try:
        jira_client = JIRA(options=jira_options, basic_auth=(jira_user, jira_api_token))
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

        # Retrieve attachment information (if any)
        attachments = subtask.fields.attachment  # This is a list of attachment objects.
        if attachments:
            attachment_lines = [
                f"{attachment.filename}: {attachment.content}" for attachment in attachments
            ]
            attachments_text = "\n".join(attachment_lines)
            print(f"Found {len(attachments)} attachment(s).")
        else:
            attachments_text = "No attachments."
            print("Found 0 attachments.")

        # Construct the prompt to send to ChatGPT
        prompt = (
            f"Ticket Description:\n{description}\n\n"
            f"Attachments:\n{attachments_text}"
        )
        print("Sending prompt to ChatGPT...")
        answer = get_chatgpt_response(prompt)
        print(f"Response for {subtask.key}:\n{answer}")

        # Post the ChatGPT response as a Jira comment
        try:
            jira_client.add_comment(subtask.key, f"\n{answer}")
            print(f"Added ChatGPT response as a comment to {subtask.key}")
        except Exception as e:
            print(f"Failed to add comment to {subtask.key}: {e}")

if __name__ == "__main__":
    process_jira_subtasks()
