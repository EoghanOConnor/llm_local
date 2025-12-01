TO run this, <br>
First generate CONFLUENCE_PERSONAL_TOKEN from Confluence Profile account.<br>
Set the Confluence URL. (JIRA url not needed for this current version)<br>
RUN: <br>
docker run --rm -i \          
  -e CONFLUENCE_URL="CONFLUENCE_URL" \<br>
  -e CONFLUENCE_PERSONAL_TOKEN="$CONFLUENCE_PERSONAL_TOKEN" \<br>
  -e CONFLUENCE_SSL_VERIFY="true" \<br>
  ghcr.io/sooperset/mcp-atlassian:latest<br>
Start the bridge to this docker: python mcp_bridge.py<br>
Start a local llm on port 8321 (setup for Granite at the moment)<br>
<br>
Finally run: python ask_granite.py<br>
