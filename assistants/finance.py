import json
from openai import OpenAI
from jira import JIRA
import os
from fpdf import FPDF
from io import BytesIO

def save_text_to_pdf(text, file_name="chatgpt_response.pdf"):
    """
    Saves the given text to a PDF file. Replaces unsupported characters.
    """
    # Replace unsupported characters (like em dash) with simpler alternatives
    text = text.replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"').replace("\u2014", "-")

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 10, text)  # Wrap text and add it to the PDF

    # Save the PDF to a temporary file
    pdf_output_path = os.path.join("/tmp", file_name)  # Save to a temporary location
    pdf.output(pdf_output_path)

    # Open the file and read it back into a BytesIO object
    with open(pdf_output_path, "rb") as f:
        pdf_output = BytesIO(f.read())

    # Optionally, remove the temporary file
    os.remove(pdf_output_path)

    return pdf_output, file_name

def load_credentials(user_name, file_path="/Users/laurawhicker/Projects/Personal-Automation-Machine/assistants/credentials.json"):
    """
    Loads credentials from a JSON file for a specific user.
    """
    try:
        with open(file_path, "r") as file:
            credentials = json.load(file)
        user_credentials = credentials.get(user_name)
        if user_credentials:
            return user_credentials
        else:
            raise ValueError(f"No credentials found for user: {user_name}")
    except Exception as e:
        print(f"Failed to load credentials for {user_name}: {e}")
        return {}
    
def load_documents(doc_paths):
    documents_content = ""
    for path in doc_paths:
        try:
            with open(path, 'r') as file:
                documents_content += f"\n\nDocument: {os.path.basename(path)}\n{file.read()}"
        except Exception as e:
            print(f"Failed to load document {path}: {e}")
    return documents_content

credentials = load_credentials(user_name='finance')


# Instantiate the OpenAI client using the instance-based interface
openai_config = credentials.get("openai", {})
openai_api_key = openai_config.get("api_key")
if not openai_api_key:
    raise ValueError("OpenAI API key not found in credentials.json")
client = OpenAI(api_key=openai_api_key)

def get_chatgpt_response(user_input, documents_content):
    """
    Calls the ChatGPT API with a system prompt and the user_input,
    then returns the assistant's reply.
    """
    system_prompt = (
        "You are a helpful financial manager for our company. Your job is to provide financial planning and tracking for the company."
        "You should respond one of three ways, asking for more information, requesting a review,"
        "or providing providing clear and detailed answers or instructions."
        "Yopu can ask for more information from '@Laura Whicker' or '@Woody Pride'"
        "you report to @Woody Pride the business lead, and ask for reviews when you think the "
        "request has been fufilled."
        "Always provide one message. Do not split your answer into multiple parts (e.g., '(Continued in the next message)')."
        "When reviewing provided info, make decisions for our next steps forward based on our business plan and financial"
        "statements. if you are unclear about the next step, tag '@Laura Whicker' for input. do this liberally."
        "Tag at the start of every comment, you should always either be giving instructions/answers"
        "to your lead, giving instructions/answers and tagging '@Laura Whicker', or asking for business info from"
        "'@Woody Pride' (business/marketing) or '@Laura Whicker' (technical, priorities )"
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_input + documents_content }
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

def process_jira_subtasks():
    """
    Connects to Jira, finds all subtask issues in "To Do" status assigned to the current user,
    and for each one sends a prompt to ChatGPT. The response is saved as a document,
    and the document is attached to the Jira issue as an attachment.
    """
    # Get Jira credentials from the loaded JSON configuration
    jira_config = credentials.get("jira", {})
    jira_server = jira_config.get("server")
    jira_user = jira_config.get("user")
    jira_api_token = jira_config.get("api_token")
    doc_paths = credentials.get("docs", {}).get("doc_paths", [])
    documents_content = load_documents(doc_paths)

    if not jira_server or not jira_user or not jira_api_token:
        print("Error: Jira credentials (server, user, api_token) must be provided in credentials.json.")
        return

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
                    f"Attachments:\n{documents_content}\n\n"
                    f"Latest Comment (current prompt):\n{latest_comment}"
                )
        else:
            prompt = f"Ticket Description:\n{description}\n\nAttachments:\n{documents_content}"

        # Fetch ChatGPT response once
        print("Sending prompt to ChatGPT...")
        answer = get_chatgpt_response(prompt, documents_content)
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


if __name__ == "__main__":
    process_jira_subtasks()