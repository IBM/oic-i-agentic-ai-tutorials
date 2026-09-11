## watsonx Orchestrate Development Rule

When working with IBM watsonx Orchestrate or watsonx Orchestrate ADK projects:

1. **Reference Guide**: Always check `wxo-implementation-guide.md` for:
   - Standard project structures (tools/, agents/, generated/)
   - Implementation patterns (Document Processing, User Activity, etc.)
   - Code examples and best practices
   - Mermaid diagram requirements

2. **Project Structure**: Follow ADK conventions:
   - New root directory for the project
   - tools/ for flows and Python tools
   - agents/ for YAML configurations
   - import-all.sh for deployment
   - README.md with architecture + workflow diagrams

3. **Key Patterns**:
   - Use @flow decorator for flows
   - Use @tool decorator for Python tools
   - Include inline KVP schemas for document processing
   - Create native agents for document handling
   - Preferably use Command Line Interface to import the agents and tools

4. **MCP Server Integration**:
   - Use `wxo-docs` MCP server to search IBM watsonx Orchestrate ADK documentation
   - Leverage MCP tools for finding API references, code examples, and implementation guides
   - Query the knowledge base when uncertain about ADK features or best practices
