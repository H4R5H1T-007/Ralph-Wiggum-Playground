import operator
from typing import Annotated, List, Dict, Any, Union
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage

def merge_dicts(a: Dict, b: Dict) -> Dict:
    return {**a, **b}

class WorkerTask(TypedDict):
    """Represents a single task delegated to a worker."""
    task_id: str
    description: str
    assigned_worker_id: str
    status: str
    result: Union[str, None]

class AgentState(TypedDict):
    """The global state of the Ralph Agent graph."""
    # Chat history
    messages: Annotated[List[BaseMessage], operator.add]
    
    # The Implementation Plan context
    plan: str
    
    # Tasks identified by the Manager that need to be done in parallel
    pending_tasks: List[WorkerTask]
    
    # Results collected from workers (task_id -> result)
    # merged using merge_dicts to allow parallel updates
    results: Annotated[Dict[str, Any], merge_dicts]
    
    # Internal flags
    iteration: int
