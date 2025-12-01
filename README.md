TO run this,
First generate CONFLUENCE_PERSONAL_TOKEN from Confluence Profile account.
Set the Confluence URL. (JIRA url not needed for this current version)
RUN: 
docker run --rm -i \          
  -e CONFLUENCE_URL="CONFLUENCE_URL" \
  -e CONFLUENCE_PERSONAL_TOKEN="$CONFLUENCE_PERSONAL_TOKEN" \
  -e CONFLUENCE_SSL_VERIFY="true" \
  ghcr.io/sooperset/mcp-atlassian:latest
Start the bridge to this docker: python mcp_bridge.py
Start a local llm on port 8321 (setup for Granite at the moment)

Finally run: python ask_granite.py
