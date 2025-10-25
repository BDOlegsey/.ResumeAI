from langgraph.graph import StateGraph, END
from models import AgentState, UserData # Импортируем UserData из models
from agents import main_agent_node, search_agent_node, generator_agent_node, checker_agent_node
from database import init_db
import os
from docx import Document # python-docx for .docx generation
import logging
import os # Need to import os here as well for config access

logger = logging.getLogger(__name__)

def main():
    # Initialize the database
    init_db()

    # Create the workflow graph
    workflow = StateGraph(AgentState)

    # Add nodes for each agent
    workflow.add_node("main_agent", main_agent_node)
    workflow.add_node("search_agent", search_agent_node)
    workflow.add_node("generator_agent", generator_agent_node)
    workflow.add_node("checker_agent", checker_agent_node)

    # Define the conditional edges logic
    def should_continue_validation(state: AgentState):
        """Decide whether to continue the generation/checking loop."""
        if state.error_message:
            logger.error(f"Workflow stopped due to error: {state.error_message}")
            return "error" # Define an 'error' path or go to END
        if state.resume_draft and state.resume_draft.is_validated:
            return "validated"
        elif state.resume_draft and state.iteration_count >= state.max_iterations:
            logger.warning(f"Max iterations ({state.max_iterations}) reached for {state.current_employer}. Proceeding with last draft.")
            return "validated" # Or "max_iterations_reached" if you want a different path
        else:
            return "not_validated"

    def should_process_next_employer(state: AgentState):
        """Decide whether to process the next employer or finish."""
        if state.error_message:
             return "error"
        # Check if the current employer's resume is validated and saved
        # This assumes the saver node runs after validation
        # A simpler check: if current_employer is the last one and it's done, END
        if state.current_employer == state.user_data.employers[-1]:
            return "end"
        else:
            return "continue" # Go back to main_agent for the next employer

    # Define edges
    workflow.add_edge("main_agent", "search_agent")
    workflow.add_edge("search_agent", "generator_agent")
    workflow.add_conditional_edges(
        "checker_agent",
        should_continue_validation,
        {
            "validated": "saver_node", # Add saver node after validation
            "not_validated": "generator_agent", # Loop back to generator
            "error": END
        }
    )
    # Add conditional edge from saver to decide next step
    workflow.add_conditional_edges(
        "saver_node",
        should_process_next_employer,
        {
            "continue": "main_agent", # Go back to main agent for next employer
            "end": END,
            "error": END
        }
    )
    # Add saver node
    workflow.add_node("saver_node", save_resume_node)

    # Set the starting point
    workflow.set_entry_point("main_agent")

    # Compile the graph
    app = workflow.compile()

    # --- Simulate User Input (Prompt) ---
    # Define the input data as per the prompt description
    user_input_data = {
        "user_data": {
            "employers": ["TechCorp", "InnovateX"],
            "job_title": "Senior Software Engineer",
            "experience": "5+ years developing web applications using Python, JavaScript, and cloud technologies. Led a team of 3 developers on a critical project.",
            "skills": "Python, JavaScript, React, Node.js, AWS, Docker, Git, Agile/Scrum",
            "achievements": "Reduced application load time by 40%. Implemented CI/CD pipeline increasing deployment frequency by 50%.",
            "attachments": [] # Add base64 strings if needed
        }
    }

    # Initialize the state with user data
    initial_state = AgentState(user_data=UserData(**user_input_data["user_data"]))

    # Run the workflow
    logger.info("Starting the multi-agent resume generation workflow.")
    try:
        final_state = app.invoke(initial_state)
        logger.info("Workflow completed.")
        if final_state.error_message:
            logger.error(f"Final state error: {final_state.error_message}")
        else:
            logger.info(f"Resumes generated successfully. Check the '{final_state.output_file_path}' directory if applicable.")
    except Exception as e:
        logger.error(f"Workflow execution failed: {e}")


def save_resume_node(state: AgentState) -> AgentState:
    """Saves the validated resume draft to a file."""
    logger.info(f"Saving validated resume for {state.current_employer}.")
    
    if not state.resume_draft or not state.resume_draft.is_validated:
        logger.error("Save node called but resume draft is not validated.")
        state.error_message = "Save node called but resume draft is not validated."
        return state

    # Ensure output directory exists
    if not os.path.exists(state.user_data.output_dir):
        os.makedirs(state.user_data.output_dir)

    filename = f"resume_{state.current_employer.replace(' ', '_')}_{state.user_data.job_title.replace(' ', '_')}.docx"
    filepath = os.path.join(state.user_data.output_dir, filename)

    try:
        doc = Document()
        doc.add_heading(f'Resume for {state.user_data.job_title} at {state.current_employer}', 0)
        # Add the draft content as paragraphs
        for line in state.resume_draft.draft_content.split('\n'):
            if line.strip(): # Avoid adding empty paragraphs for blank lines
                doc.add_paragraph(line)
        doc.save(filepath)
        logger.info(f"Resume saved to {filepath}")
        state.output_file_path = filepath
    except Exception as e:
        logger.error(f"Failed to save resume for {state.current_employer}: {e}")
        state.error_message = f"Failed to save resume: {e}"

    return state

if __name__ == "__main__":
    main()