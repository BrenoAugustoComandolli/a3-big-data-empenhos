import json
import pandas as pd
import os
import logging
from dotenv import load_dotenv
from db_connection import create_connection
from pathlib import Path

# Configuração do logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

ASSETS_PATH = Path(__file__).parent.parent / 'assets' / 'mapeamento.json'
SQL_SELECT = "SELECT {campo_id} FROM {nome_tabela} WHERE {campo_unico} = %s"
SQL_INSERT = "INSERT INTO {nome_tabela} ({colunas}) VALUES ({placeholders});"

load_dotenv()

def carregar_planilha():
    """Carrega a planilha a partir do caminho especificado nas variáveis de ambiente.
    
    Returns:
        pd.DataFrame: Dados da planilha.
    """
    caminho_arquivo = os.getenv('CAMINHO_PLANILHA')
    if not caminho_arquivo:
        raise FileNotFoundError("Planilha não encontrada")
    
    logging.info("Carregando planilha...")
    return pd.read_excel(caminho_arquivo)

def carregar_mapeamento():
    """Carrega o mapeamento de colunas e FKs para tabelas do arquivo JSON.
    
    Returns:
        dict: Mapeamento de colunas e chaves estrangeiras.
    """
    logging.info("Carregando mapeamento...")
    with open(ASSETS_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def processar_dados(dados_planilha, mapeamento):
    """Processa os dados da planilha, inserindo os registros no banco de dados.
    
    Args:
        dados_planilha: Dados da planilha em formato DataFrame.
        mapeamento: Mapeamento de colunas e FKs.
    """
    logging.info("Iniciando o processamento dos dados...")
    for index, linha in dados_planilha.iterrows():
        try:
            connection = create_connection()
            if not connection:
                logging.error("Falha na conexão com o banco de dados")
                return
            
            tratar_inserts_linha(connection, linha, mapeamento)
        except Exception as e:
            logging.error(f"Erro ao processar linha {index}: {e}", exc_info=True)
        finally:
            if connection:
                connection.close()

def tratar_inserts_linha(connection, linha, mapeamento):
    """Processa uma linha do DataFrame e realiza inserções conforme o mapeamento.
    
    Args:
        connection: Conexão com o banco de dados.
        linha: Linha do DataFrame a ser processada.
        mapeamento: Mapeamento de colunas e FKs.
    """
    idsCriados = {}
    for tabela, propriedades in mapeamento.items():
        dados = extrair_dados(linha, propriedades)
        dados = adicionar_chaves_estrangeiras(dados, idsCriados, propriedades)
        inserir_registro(connection, tabela, dados, propriedades, idsCriados)

def extrair_dados(linha, propriedades):
    """Extrai dados da linha do DataFrame conforme o mapeamento de colunas.
    
    Args:
        linha: Linha do DataFrame.
        propriedades: Propriedades da tabela conforme o mapeamento.
    
    Returns:
        dict: Dados extraídos.
    """
    dados = {}
    if 'colunas' in propriedades and propriedades['colunas']:
        for campo_origem, campo_destino in propriedades['colunas'].items():
            dados[campo_destino] = linha.get(campo_origem)
    return dados

def adicionar_chaves_estrangeiras(dados, idsCriados, propriedades):
    """Adiciona valores de chaves estrangeiras aos dados.
    
    Args:
        dados: Dados da tabela.
        idsCriados: IDs já criados para as tabelas referenciadas.
        propriedades: Propriedades da tabela conforme o mapeamento.
    
    Returns:
        dict: Dados atualizados com chaves estrangeiras.
    """
    if 'fks' in propriedades and propriedades['fks']:
        for campo_fk, tabela_ref in propriedades['fks'].items():
            if tabela_ref in idsCriados:
                dados[campo_fk] = idsCriados[tabela_ref]
    return dados

def inserir_registro(connection, tabela, dados, propriedades, idsCriados):
    """Insere um registro na tabela e atualiza IDs criados.
    
    Args:
        connection: Conexão com o banco de dados.
        tabela: Nome da tabela.
        dados: Dados a serem inseridos.
        propriedades: Propriedades da tabela conforme o mapeamento.
        idsCriados: IDs já criados para as tabelas referenciadas.
    """
    if 'campo_unico' in propriedades and propriedades['campo_unico']:
        logging.info(f"Inserindo dados na tabela {tabela}...")
        id_inserido = inserir_e_obter_id(connection, tabela.split('#')[0].strip(), dados, propriedades['campo_unico'], propriedades.get('id_coluna'))
        if id_inserido is not None:
            idsCriados[tabela] = id_inserido

def inserir_e_obter_id(connection, nome_tabela, dados, campo_unico, campo_id):
    """Insere dados em uma tabela e retorna o ID do registro inserido ou o ID existente.
    
    Args:
        connection: Conexão com o banco de dados.
        nome_tabela: Nome da tabela.
        dados: Dados a serem inseridos.
        campo_unico: Nome do campo único para verificação.
        campo_id: Nome do campo de ID.
    
    Returns:
        int or None: ID do registro inserido ou existente, ou None se não houver dados.
    """
    if campo_unico and campo_unico in dados and pd.notnull(dados[campo_unico]):
        id_existente = obter_id_existente(connection, nome_tabela, campo_unico, dados[campo_unico], campo_id)
        if id_existente:
            logging.info(f"Registro existente encontrado para {campo_unico}: {id_existente}")
            return id_existente
    
    dados_filtrados = {k: v for k, v in dados.items() if pd.notnull(v)}
    if not dados_filtrados:
        return None
    
    colunas = ', '.join(dados_filtrados.keys())
    placeholders = ', '.join(['%s'] * len(dados_filtrados))
    sql = SQL_INSERT.format(nome_tabela=nome_tabela, colunas=colunas, placeholders=placeholders)
    
    try:
        cursor = connection.cursor()
        cursor.execute(sql, tuple(dados_filtrados.values()))
        connection.commit()
        id_inserido = cursor.lastrowid
    except Exception as e:
        logging.error(f"Ocorreu um erro ao inserir na tabela {nome_tabela}, erro: {e}")
        return None
    finally:
        cursor.close()
    
    logging.info(f"Registro inserido na tabela {nome_tabela} com ID: {id_inserido}")
    return id_inserido

def obter_id_existente(connection, nome_tabela, campo_unico, valor_unico, campo_id):
    """Verifica se um registro com o valor único especificado já existe e retorna seu ID.
    
    Args:
        connection: Conexão com o banco de dados.
        nome_tabela: Nome da tabela.
        campo_unico: Nome do campo único.
        valor_unico: Valor a ser verificado.
        campo_id: Nome do campo de ID.
    
    Returns:
        int or None: ID do registro existente ou None se não existir.
    """
    
    try:
        cursor = connection.cursor()
        sql = SQL_SELECT.format(campo_id=campo_id, nome_tabela=nome_tabela, campo_unico=campo_unico)
        cursor.execute(sql, (valor_unico,))
        resultado = cursor.fetchall()
        return resultado[0][0] if resultado else None
    except Exception as e:
        logging.error(f"Ocorreu um erro ao obter ID existente: {e}")
        return None
    finally:
        cursor.close()

def main():
    """Função principal para carregar a planilha e processar os dados."""
    try:
        logging.info("Iniciando a integração...")
        dados_planilha = carregar_planilha()
        mapeamento = carregar_mapeamento()
        processar_dados(dados_planilha, mapeamento)
        logging.info("Integração concluída com sucesso.")
    except Exception as e:
        logging.error(f"Ocorreu um erro na execução principal: {e}")

if __name__ == "__main__":
    main()
