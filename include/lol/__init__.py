"""Ingesta de partidas de League of Legends desde la Riot Games API.

Proyecto Integrador — Ciencia de Datos — UTN FRM — 2026 — Grupo 5K09-02.

Ningún módulo de este paquete importa Airflow. Es deliberado: así se puede
testear con pytest plano y reusar tal cual en las Unidades 2, 3 y 4, donde
no hay un DAG alrededor. Lo que necesita configuración la recibe por
parámetro desde la tarea que lo llama.
"""
