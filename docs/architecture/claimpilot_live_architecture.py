"""Generate the ClaimPilot live Azure architecture diagram.

Requires Graphviz and the `diagrams` Python package:

    pip install "diagrams>=0.25.0"
    python docs/architecture/claimpilot_live_architecture.py
"""

from __future__ import annotations

from pathlib import Path

from diagrams import Cluster, Diagram, Edge
from diagrams.azure.analytics import LogAnalyticsWorkspaces
from diagrams.azure.compute import ContainerApps, ContainerRegistries
from diagrams.azure.database import CosmosDb
from diagrams.azure.integration import ServiceBus
from diagrams.azure.ml import AzureOpenAI, AzureSpeechService, CognitiveServices
from diagrams.azure.security import KeyVaults
from diagrams.azure.storage import BlobStorage
from diagrams.azure.web import Search, Signalr
from diagrams.onprem.client import Users
from diagrams.programming.framework import FastAPI, React

OUTPUT = Path(__file__).with_suffix("")

graph_attr = {
    "fontsize": "24",
    "pad": "0.25",
    "ranksep": "0.65",
    "nodesep": "0.5",
    "splines": "ortho",
    "concentrate": "false",
    "compound": "true",
}

node_attr = {
    "fontsize": "12",
}

edge_attr = {
    "fontsize": "10",
}


with Diagram(
    "ClaimPilot Live Azure Architecture",
    filename=str(OUTPUT),
    outformat="png",
    show=False,
    direction="LR",
    graph_attr=graph_attr,
    node_attr=node_attr,
    edge_attr=edge_attr,
):
    adjuster = Users("Claimant / Adjuster")
    frontend = React("Next.js Dashboard\nContainer App")
    api = FastAPI("FastAPI API\nContainer App")

    with Cluster("Evidence Store"):
        intake = BlobStorage("Blob Storage\nclaims-intake")

    with Cluster("Async Processing"):
        queue = ServiceBus("Service Bus\nclaim queue")
        worker = ContainerApps("Pipeline Worker\nContainer App")

    with Cluster("Azure AI + Foundry"):
        doc_intel = CognitiveServices("Document Intelligence\nPDF extraction")
        vision = AzureOpenAI("Foundry Vision\nphoto analysis")
        speech = AzureSpeechService("Speech STT\nTranslator")
        search = Search("Azure AI Search\npolicies + prior claims")
        foundry = AzureOpenAI("Foundry Agents\nClassify -> Extract -> Fraud -> Decide")
        voice_live = AzureSpeechService("Voice Live\ngpt-realtime")

    with Cluster("Platform Services"):
        registry = ContainerRegistries("Azure Container\nRegistry")
        vault = KeyVaults("Key Vault\nsecrets")
        logs = LogAnalyticsWorkspaces("Log Analytics\nApp Insights")
        registry - Edge(style="invis") - vault - Edge(style="invis") - logs

    with Cluster("Runtime State"):
        state = CosmosDb("Cosmos DB\nclaim state")
        realtime = Signalr("Azure SignalR\nprogress events")

    adjuster >> frontend >> api

    api >> Edge(label="enqueue claim") >> queue >> worker
    api >> Edge(label="store uploads") >> intake
    intake >> Edge(label="evidence files") >> worker

    worker >> Edge(label="form") >> doc_intel >> foundry
    worker >> Edge(label="photos") >> vision >> foundry
    worker >> Edge(label="audio") >> speech >> foundry
    worker >> Edge(label="policy + history") >> search >> foundry

    foundry >> Edge(label="decision + reasoning") >> state
    foundry >> Edge(label="status events") >> realtime

    api >> Edge(label="adjuster voice relay") >> voice_live
    voice_live >> Edge(label="claim lookup tools") >> state
