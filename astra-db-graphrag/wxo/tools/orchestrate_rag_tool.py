from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission
from ibm_watsonx_orchestrate.run import connections
from ibm_watsonx_orchestrate.agent_builder.connections import ConnectionType, ExpectedCredentials
from langchain_astradb import AstraDBVectorStore
from langchain_ibm import WatsonxEmbeddings
from graph_retriever.strategies import Eager
from langchain_graph_retriever import GraphRetriever
from pydantic import BaseModel, Field
from typing import List

class RAGSearchResults(BaseModel):
    """
    This class represents the search results.
    """
    context_data: str | None = Field(description="Context data for the question")
    document_titles: List[str] | None = Field(description="A list of document titles")

@tool(name="orchestrate_rag_tool", 
      permission=ToolPermission.READ_ONLY,
      expected_credentials=[
          ExpectedCredentials(
            app_id = "astradb",
            type = ConnectionType.KEY_VALUE),
          ExpectedCredentials(
            app_id = "watsonx",
            type = ConnectionType.KEY_VALUE)
        ]
)
def doc_search_rag(question:str) -> RAGSearchResults:
    """
    Retrieve context data to help answer a question using Graph RAG

    :returns: Context data
    """

    astradb_conn = connections.key_value("astradb")
    watsonx_conn = connections.key_value("watsonx")

    ASTRA_DB_API_ENDPOINT = astradb_conn['ASTRA_DB_API_ENDPOINT']
    ASTRA_DB_APPLICATION_TOKEN = astradb_conn['ASTRA_DB_APPLICATION_TOKEN']
    WATSONX_APIKEY = watsonx_conn['WATSONX_APIKEY']
    WATSONX_PROJECT_ID = watsonx_conn['WATSONX_PROJECT_ID']
    
    embeddings = WatsonxEmbeddings(
        model_id="ibm/granite-embedding-278m-multilingual",
        url="https://us-south.ml.cloud.ibm.com",
        apikey=WATSONX_APIKEY,
        project_id=WATSONX_PROJECT_ID,
    )

    COLLECTION = "wxo_docs"
    vectorstore = AstraDBVectorStore(
        embedding=embeddings,
        collection_name=COLLECTION,
        pre_delete_collection=False,
        api_endpoint=ASTRA_DB_API_ENDPOINT,
        token=ASTRA_DB_APPLICATION_TOKEN,
    )

    # Request up to 10 results, all from semantic search
    simple_retriever = GraphRetriever(
        store = vectorstore,
        edges = [("hyperlinks", "url")],
        strategy = Eager(k=5, start_k=5, max_depth=0)
    )
    
    # invoke the query
    query_results = simple_retriever.invoke(question)
    
    # Concatenate the results
    results_str = ""
    chunks_used = []
    for result in query_results:
        results_str += result.page_content
        results_str += "\n\n------------"
        chunks_used.append(result.metadata['id'])

    result = RAGSearchResults(
        context_data=results_str,
        document_titles=chunks_used
    )

    return result