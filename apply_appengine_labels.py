#!/usr/bin/env python3
"""
Script de tageamento em serviços do Google App Engine.

Fluxo da aplicação:
1. Lê um arquivo CSV contendo os serviços e suas respectivas labels.
2. Valida se o CSV possui todas as colunas obrigatórias.
3. Monta as labels para cada serviço.
4. Utiliza a App Engine Admin API para atualizar apenas o campo de labels.
5. Exibe um resumo da execução.

Uso:
    python label_appengine_services.py --project SEU_PROJECT_ID --csv labels.csv
    python label_appengine_services.py --project SEU_PROJECT_ID --csv labels.csv --dry-run
 
Pre-requisitos:
    pip install google-api-python-client google-auth
    gcloud auth application-default login
"""

# Biblioteca para criação de argumentos via linha de comando
import argparse

# Biblioteca para leitura de arquivos CSV
import csv

# Biblioteca responsável pelos logs da aplicação
import logging

# Biblioteca utilizada para expressões regulares
import re

# Biblioteca utilizada para encerrar a aplicação quando necessário
import sys

# Cliente oficial da Google API
from googleapiclient import discovery

# Exceção lançada quando ocorre erro na chamada da API
from googleapiclient.errors import HttpError

# Obtém automaticamente as credenciais do usuário autenticado
from google.auth import default as google_auth_default


# Configuração padrão do logger da aplicação
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

logger = logging.getLogger(__name__)


# Colunas obrigatórias esperadas no arquivo CSV
CSV_COLUMNS = [
    "Nome do recurso",
    "Team",
    "Cost Center",
    "Country",
]


def sanitize_label_value(value: str) -> str:
    """
    Adequa os valores para o padrão aceito pelo Google Cloud.

    Regras:
    - letras minúsculas
    - números
    - underscore (_)
    - hífen (-)
    - máximo de 63 caracteres
    """

    value = value.strip().lower()
    value = value.replace(" ", "-")
    value = re.sub(r"[^a-z0-9_-]", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")

    return value[:63]


def build_labels_from_row(row: dict) -> dict:
    """
    Monta o dicionário de labels que será enviado para a API.
    """

    return {
        "team": sanitize_label_value(row["Team"]),
        "cost-center": sanitize_label_value(row["Cost Center"]),
        "country": sanitize_label_value(row["Country"]),
    }


def read_csv_rows(csv_path: str) -> list:
    """
    Lê o arquivo CSV e valida se todas as colunas obrigatórias existem.
    Também ignora linhas sem o nome do recurso.
    """

    with open(csv_path, newline="", encoding="utf-8") as f:

        reader = csv.DictReader(f)

        # Verifica se todas as colunas obrigatórias existem
        missing = [
            c
            for c in CSV_COLUMNS
            if c not in (reader.fieldnames or [])
        ]

        if missing:
            raise ValueError(
                f"CSV não contém as colunas esperadas: {missing}"
            )

        rows = []

        # Percorre cada linha do CSV
        for i, row in enumerate(reader, start=2):

            nome_recurso = (
                row.get("Nome do recurso") or ""
            ).strip()

            # Ignora linhas sem nome do recurso
            if not nome_recurso:
                logger.warning(
                    "Linha %s ignorada: Nome do recurso vazio.",
                    i,
                )
                continue

            rows.append(row)

        return rows


def apply_labels(
    service,
    project_id: str,
    service_id: str,
    labels: dict,
    dry_run: bool,
):
    """
    Atualiza as labels do Service utilizando
    a App Engine Admin API.
    """

    # Apenas simula a execução
    if dry_run:
        logger.info(
            "[DRY-RUN] service=%s labels=%s",
            service_id,
            labels,
        )
        return

    # Chamada PATCH para atualizar somente o campo "labels"
    request = service.apps().services().patch(
        appsId=project_id,
        servicesId=service_id,
        body={"labels": labels},
        updateMask="labels",
    )

    operation = request.execute()

    logger.info(
        "Labels aplicadas no service '%s'. Operação: %s",
        service_id,
        operation.get("name", "?"),
    )


def main():
    """
    Função principal responsável por orquestrar
    toda a execução da aplicação.
    """

    parser = argparse.ArgumentParser(
        description="Aplica labels em serviços do App Engine."
    )

    parser.add_argument(
        "--project",
        required=True,
        help="ID do projeto Google Cloud.",
    )

    parser.add_argument(
        "--csv",
        required=True,
        help="Arquivo CSV contendo os serviços.",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Executa apenas uma simulação.",
    )

    args = parser.parse_args()

    # Lê o CSV
    try:
        rows = read_csv_rows(args.csv)

    except (FileNotFoundError, ValueError) as e:

        logger.error(e)

        sys.exit(1)

    if not rows:

        logger.warning(
            "Nenhuma linha válida encontrada."
        )

        return

    # Obtém automaticamente as credenciais do usuário
    credentials, _ = google_auth_default()

    # Cria o cliente da App Engine Admin API
    service = discovery.build(
        "appengine",
        "v1",
        credentials=credentials,
        cache_discovery=False,
    )

    sucesso = 0
    falha = 0

    # Percorre cada linha do CSV
    for row in rows:

        service_id = row["Nome do recurso"].strip()

        labels = build_labels_from_row(row)

        try:

            apply_labels(
                service,
                args.project,
                service_id,
                labels,
                args.dry_run,
            )

            sucesso += 1

        except HttpError as e:

            logger.error(
                "Falha ao atualizar '%s': %s",
                service_id,
                e,
            )

            falha += 1

    logger.info(
        "Concluído. Sucesso: %s | Falhas: %s",
        sucesso,
        falha,
    )

    if falha:
        sys.exit(1)


if __name__ == "__main__":
    main()