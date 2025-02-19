# Personal-Automation-Machine
["Pam! Pam! Pam!"](https://www.youtube.com/watch?v=7AFPj9PZP8k) ~Micheal Scott

PAM is an Airflow based gpt assitant. It is set up to act as a Jira User providing tailored asistance and chats via jira comments. 

## Built With
* [![Docker][docker-logo]][docker-url]
* [![Airflow][Airflow-logo]][Airflow-url]

<p align="right">(<a href="#readme-top">back to top</a>)</p>

### Instalation

1. Install Requirements 
   ```sh
   pip install -r requirements.txt
   ```
2. Install Docker Desktop
   [Docker Download](https://www.docker.com/products/docker-desktop/)
   
3. Build Docker Container
   ```sh
   docker compose up -d --build
   ```

### Use

1. Start Docker Images
   
   <img width="800" alt="Screenshot 2025-02-18 at 1 53 22 PM" src="https://github.com/user-attachments/assets/6ed2a62b-ae49-4915-b90d-0a1eb54bcee8" />
2. Create [Jira](https://www.atlassian.com) User For each assistant you intend to create, more can be added later. 
3. Using the creds_template.json input
   * the name of your assistant
   * your openai api key
   * the jira server, username, and api key for the new user
   * the prompt describing how you would like this user to interact and respond. 
4. navigate to [http://localhost:8080/variable/list/](http://localhost:8080/variable/list/)
5. add a variable called creds and copy the ceds.json file contents to the variable Val.
6. navigate to [http://localhost:8080/home](http://localhost:8080/home)
   <img width="800" alt="Screenshot 2025-02-18 at 9 29 08 PM" src="https://github.com/user-attachments/assets/8131afe0-89e1-4b43-a7b5-6dc25f8abebf" />

7. Run pam_dag and Assign a Jira ticket with a description to an assistant's jira user, every minute you should expect a response to either you or another assistant (See Example for expected interactions).
    
   <img width="600" alt="Screenshot 2025-02-18 at 9 20 48 PM" src="https://github.com/user-attachments/assets/1c42d0c6-42e6-475a-b21f-02135c7ae9c8" />



[docker-logo]: https://www.docker.com/app/uploads/2023/08/logo-guide-logos-1.svg
[docker-url]: https://www.docker.com/
[airflow-logo]: https://upload.wikimedia.org/wikipedia/commons/thumb/d/de/AirflowLogo.png/440px-AirflowLogo.png
[airflow-url]: https://airflow.apache.org/



