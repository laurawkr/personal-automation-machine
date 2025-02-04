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

def load_credentials(file_path="/Users/laurawhicker/Projects/Personal-Automation-Machine/assistants/credentials.json"):
    """
    Loads credentials from a JSON file.
    The JSON file should have the following structure:
    {
      "openai": {
        "api_key": "your_openai_api_key_here"
      },
      "jira": {
        "server": "https://your_jira_server",
        "user": "your_jira_username",
        "api_token": "your_jira_api_token"
      }
    }
    """
    try:
        with open(file_path, "r") as file:
            return json.load(file)
    except Exception as e:
        print(f"Failed to load credentials from {file_path}: {e}")
        return {}

# Load credentials from the JSON file
credentials = load_credentials()

# Instantiate the OpenAI client using the instance-based interface
openai_config = credentials.get("openai", {})
openai_api_key = openai_config.get("api_key")
if not openai_api_key:
    raise ValueError("OpenAI API key not found in credentials.json")
client = OpenAI(api_key=openai_api_key)

def get_chatgpt_response(user_input):
    """
    Calls the ChatGPT API with a system prompt and the user_input,
    then returns the assistant's reply.
    """
    system_prompt = (
        "You are a helpful personal assistant who helps me manage my business. Provide clear and detailed answers, "
        "and if necessary, ask clarifying questions. "
        "Always provide one message. Do not split your answer into multiple parts (e.g., '(Continued in the next message)')."
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
                    f"Ticket Description:\n{description}\n\n"
                    f"Attachments:\n{attachments_text}\n\n"
                    f"Previous Comments (in order):\n{previous_comments}\n\n"
                    f"Latest Comment (current prompt):\n{latest_comment}"
                )
            else:
                latest_comment = sorted_comments[0].body if hasattr(sorted_comments[0], "body") else sorted_comments[0].get("body", "")
                prompt = (
                    f"Ticket Description:\n{description}\n\n"
                    f"Attachments:\n{attachments_text}\n\n"
                    f"Latest Comment (current prompt):\n{latest_comment}"
                )
        else:
            prompt = f"Ticket Description:\n{description}\n\nAttachments:\n{attachments_text}"

        print("Sending prompt to ChatGPT...")
        answer = get_chatgpt_response(prompt)
        print(f"Response for {subtask.key}:\n{answer}")

        # Post the ChatGPT response as a Jira comment
        try:
            jira_client.add_comment(subtask.key, f"\nChanges made:\n{answer}")
            print(f"Added ChatGPT response as a comment to {subtask.key}")
        except Exception as e:
            print(f"Failed to add comment to {subtask.key}: {e}")

        # Generate a PDF from the ChatGPT response
        pdf_output, file_name = save_text_to_pdf(answer, file_name="chatgpt_response.pdf")
        
        # Attach the PDF document to the Jira issue
        try:
            jira_client.add_attachment(issue=subtask, attachment=pdf_output, filename=file_name)
            print(f"Document attached to {subtask.key}")
        except Exception as e:
            print(f"Failed to attach document to {subtask.key}: {e}")

if __name__ == "__main__":
    process_jira_subtasks()
