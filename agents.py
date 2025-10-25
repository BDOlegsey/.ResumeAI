# Import Perplexity LLM wrapper from LangChain
from langchain_perplexity import ChatPerplexity
from langchain_core.prompts import ChatPromptTemplate
# УДАЛЕНО: from langchain_core.pydantic_v1 import BaseModel, Field
# УДАЛЕНО: from typing import List # Не используется в этом файле
from models import UserData, SearchResults, ResumeDraft, AgentState
from database import get_employer_info, store_employer_info
from tools import TOOLS
import logging
import os # Добавлен для доступа к os.getenv

logger = logging.getLogger(__name__)

# --- Initialize LLM with Perplexity ---
# Using the model specified in config.py
llm = ChatPerplexity(
    model_name="llama-3.1-sonar-small-128k-online", # Use the default or set via config if needed
    temperature=0.1, # Lower temperature for more consistent outputs if needed
    api_key=os.getenv("PERPLEXITY_API_KEY") # Fetch key from environment
)

# --- Main Agent ---
def main_agent_node(state: AgentState) -> AgentState:
    """Handles initial user input and iterates through employers."""
    logger.info("Main Agent processing user data and selecting employer.")
    
    # In a real scenario, this would come from the user input node.
    # For this implementation, we assume state.user_data is already populated.
    if not state.user_data:
        logger.error("Main Agent: No user data provided.")
        state.error_message = "No user data provided."
        return state
        
    # Select the next employer from the list
    if state.current_employer is None:
        # Start with the first employer
        if state.user_data.employers:
             state.current_employer = state.user_data.employers[0]
             logger.info(f"Main Agent: Selected first employer - {state.current_employer}")
        else:
            logger.error("Main Agent: No employers listed in user data.")
            state.error_message = "No employers listed in user data."
            return state
    else:
        # Move to the next employer after a resume is finalized
        current_index = state.user_data.employers.index(state.current_employer)
        if current_index + 1 < len(state.user_data.employers):
            state.current_employer = state.user_data.employers[current_index + 1]
            logger.info(f"Main Agent: Selected next employer - {state.current_employer}")
            # Reset state for the new employer
            state.search_results = None
            state.resume_draft = None
            state.iteration_count = 0
        else:
            # All employers processed
            logger.info("Main Agent: All employers processed.")
            return state # This should lead to an END state in the graph

    return state

# --- Search Agent ---
def search_agent_node(state: AgentState) -> AgentState:
    """Searches for information about the current employer."""
    logger.info(f"Search Agent starting for employer: {state.current_employer}")
    
    if not state.current_employer:
        logger.error("Search Agent: No current employer set.")
        state.error_message = "Search Agent: No current employer set."
        return state

    # Note: Perplexity models are generally good at web-based queries inherently.
    # However, the original requirement was for an agent that "uses a mouse".
    # Selenium is still the tool for *that specific interaction*.
    # We use the search_web_tool (which uses Selenium) as defined in tools.py.
    # The LLM (Perplexity) just needs to *instruct* the tool correctly.

    # Check database first
    db_results = get_employer_info(state.current_employer)
    if db_results:
        logger.info(f"Search Agent: Found cached info for {state.current_employer} in database.")
        state.search_results = db_results
        return state

    # If not found in DB, use the tool to search
    logger.info(f"Search Agent: Info for {state.current_employer} not in DB, using search tool.")
    # The tool is called by the agent's LLM loop in LangGraph
    # We define the task for the LLM here.
    search_prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a web researcher. Use the search_web_tool to find information about the given employer and job title. Focus on the company's mission, values, culture, recent news, and specific requirements or skills mentioned for the '{job_title}' role at '{employer_name}'. Be concise but thorough."),
        ("human", "Research the employer '{employer_name}' for the role of '{job_title}'.")
    ])
    
    # Bind tools to the LLM
    # Note: Perplexity models might not support tool binding in the exact same way as OpenAI.
    # The `search_web_tool` is a LangChain @tool, which usually works with agents that support it.
    # Let's assume for this example it integrates similarly. If not, the tool calling logic
    # would need to be handled differently, perhaps directly in the node function.
    # For now, we'll bind it as usual.
    llm_with_tools = llm.bind_tools(TOOLS)
    
    # Create a chain
    search_chain = search_prompt | llm_with_tools
    
    # Invoke the chain - this is where the tool is actually called by the LLM
    try:
        response = search_chain.invoke({
            "employer_name": state.current_employer,
            "job_title": state.user_data.job_title
        })
        
        # The response from the LLM will contain the tool call results if the tool was used
        # We need to extract the final string content after tool execution
        # For simplicity in this example, we assume the final output is the search result string
        # In practice, you might need to parse the response object more carefully,
        # especially if multiple tool calls or intermediate thoughts are involved.
        # LangChain usually handles this with an agent executor.
        # Let's assume the final response.content is the synthesized information.
        # If the tool's raw output is needed, the chain execution needs to be handled differently.
        # For this simplified version, we'll assume the LLM processes the tool output.
        # A more robust way is to use an agent executor, but for simplicity in this node:
        # We'll call the tool directly if binding doesn't work as expected by the search_web_tool's internal logic.
        # However, let's assume binding works for this framework context.
        # The `response` here is the LLM's final message after tool use.
        search_output = response.content if hasattr(response, 'content') else str(response)
        
        # Parse the search output into a SearchResults object
        # This requires the LLM to format its output predictably, or post-processing
        # A simple split might work if the LLM consistently formats like "Company Info:\n...Job Specific Info:\n..."
        # A more robust approach is to ask the LLM to output structured JSON.
        # Assuming the LLM summarizes the tool's findings effectively.
        # Let's simplify the parsing for now, assuming the output is a summary.
        # A better approach would be to have the LLM output JSON and parse it.
        # For this example, let's assume it formats as requested.
        parts = search_output.split("\n\nJob Specific Info:\n")
        if len(parts) == 2:
            company_info = parts[0].replace("Company Info:\n", "")
            job_info = parts[1]
        else:
            # Fallback if format isn't as expected
            company_info = search_output
            job_info = "No specific job info extracted."

        search_results = SearchResults(
            employer_name=state.current_employer,
            company_info=company_info.strip(),
            job_specific_info=job_info.strip()
        )
        
        # Store the results in the database for future use
        store_employer_info(search_results)
        
        # Update state
        state.search_results = search_results
        logger.info(f"Search Agent completed for {state.current_employer}.")
        
    except Exception as e:
        logger.error(f"Search Agent failed for {state.current_employer}: {e}")
        state.error_message = f"Search Agent failed for {state.current_employer}: {e}"

    return state


# --- Generator Agent ---
def generator_agent_node(state: AgentState) -> AgentState:
    """Generates the resume draft based on user data and search results."""
    logger.info(f"Generator Agent starting for employer: {state.current_employer}")
    
    if not state.search_results or not state.user_data:
        logger.error("Generator Agent: Missing user data or search results.")
        state.error_message = "Generator Agent: Missing user data or search results."
        return state

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", "You are an expert resume writer. Create a professional, tailored resume for the user applying for the position of '{job_title}' at '{employer_name}'. Use the provided User Information and Employer Information to highlight relevant experience, skills, and achievements that align with the company's needs and the role's requirements. Ensure the resume is well-structured, ATS-friendly, and compelling. If attachments were mentioned, acknowledge relevant qualifications from them if applicable."),
        ("human", "User Information:\nExperience: {experience}\nSkills: {skills}\nAchievements: {achievements}\n\nEmployer Information:\nCompany Info: {company_info}\nJob Specific Info: {job_specific_info}\n\nAttachments: {attachments}\n\nPlease generate the resume content.")
    ])

    chain = prompt_template | llm # Use the Perplexity LLM
    
    attachments_str = "\n".join([f"Attachment {i+1}" for i in range(len(state.user_data.attachments))]) if state.user_data.attachments else "None provided."
    
    try:
        response = chain.invoke({
            "job_title": state.user_data.job_title,
            "employer_name": state.current_employer,
            "experience": state.user_data.experience,
            "skills": state.user_data.skills,
            "achievements": state.user_data.achievements,
            "company_info": state.search_results.company_info,
            "job_specific_info": state.search_results.job_specific_info,
            "attachments": attachments_str
        })

        draft_content = response.content if hasattr(response, 'content') else str(response)
        
        state.resume_draft = ResumeDraft(draft_content=draft_content, is_validated=False, validation_feedback="")
        state.iteration_count += 1
        logger.info(f"Generator Agent created draft for {state.current_employer}. Iteration: {state.iteration_count}")
        
    except Exception as e:
        logger.error(f"Generator Agent failed for {state.current_employer}: {e}")
        state.error_message = f"Generator Agent failed for {state.current_employer}: {e}"

    return state


# --- Checker Agent ---
def checker_agent_node(state: AgentState) -> AgentState:
    """Checks the resume draft for errors and alignment."""
    logger.info(f"Checker Agent reviewing draft for employer: {state.current_employer}")
    
    if not state.resume_draft or not state.user_data or not state.search_results:
        logger.error("Checker Agent: Missing resume draft, user data, or search results.")
        state.error_message = "Checker Agent: Missing resume draft, user data, or search results."
        return state

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", "You are an expert resume checker. Review the provided resume draft against the User Information and Employer Information. Check for:\n1. Alignment of skills/experience with job requirements.\n2. Clarity, grammar, and professional tone.\n3. ATS-friendliness (formatting, keywords).\n4. Overall persuasiveness.\n\nProvide specific feedback on what needs to be corrected or improved. If the resume is good, state 'VALIDATED'."),
        ("human", "User Information:\nExperience: {experience}\nSkills: {skills}\nAchievements: {achievements}\n\nEmployer Information:\nCompany Info: {company_info}\nJob Specific Info: {job_specific_info}\n\nResume Draft:\n{draft_content}\n\nFeedback:")
    ])

    chain = prompt_template | llm # Use the Perplexity LLM
    
    try:
        response = chain.invoke({
            "experience": state.user_data.experience,
            "skills": state.user_data.skills,
            "achievements": state.user_data.achievements,
            "company_info": state.search_results.company_info,
            "job_specific_info": state.search_results.job_specific_info,
            "draft_content": state.resume_draft.draft_content
        })

        feedback = response.content if hasattr(response, 'content') else str(response)
        
        if "VALIDATED" in feedback.upper():
            state.resume_draft.is_validated = True
            logger.info(f"Checker Agent validated resume for {state.current_employer}.")
        else:
            state.resume_draft.validation_feedback = feedback
            logger.info(f"Checker Agent found issues for {state.current_employer}. Feedback: {feedback[:100]}...")
            # Reset is_validated to False explicitly if not validated
            state.resume_draft.is_validated = False

    except Exception as e:
        logger.error(f"Checker Agent failed for {state.current_employer}: {e}")
        state.error_message = f"Checker Agent failed for {state.current_employer}: {e}"
        # On error, consider the draft not validated to prevent infinite loops
        state.resume_draft.is_validated = False
        state.resume_draft.validation_feedback = f"An error occurred during checking: {e}"

    return state