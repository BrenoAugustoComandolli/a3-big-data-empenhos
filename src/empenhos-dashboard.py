import pandas as pd
from dash import Dash, html, dcc, Input, Output
import plotly.express as px
from db_connection import create_connection

class EmpenhosDashboard:
    """
    Classe responsável pela geração dos gráficos e dashboard interativo.
    """
    def __init__(self, db_connection):
        self.db = db_connection

    def get_data(self, start_date, end_date):
        """
        Coleta os dados necessários do banco de dados para os gráficos com base no intervalo de datas.
        """
        query = f"""
            SELECT
                EMP.EMP_VALOR_CONVERTIDO, 
                ORG.ORG_NOME, 
                FAV.FAV_NOME, 
                EMP.EMP_DATA_EMISSAO, 
                CDE.CDE_NOME 
            FROM TB_EMPENHO EMP
            JOIN TB_ORGAO ORG ON EMP.EMP_ORGID = ORG.ORG_ID
            JOIN TB_FAVORECIDO FAV ON EMP.EMP_FAVID = FAV.FAV_ID
            JOIN TB_CATEGORIA_DESPESA CDE ON EMP.EMP_CDEID = CDE.CDE_ID
            WHERE EMP.EMP_DATA_EMISSAO BETWEEN '{start_date}' AND '{end_date}';
        """
        cursor = self.db.cursor()
        cursor.execute(query)
        data = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        df = pd.DataFrame(data, columns=columns)
        cursor.close()
        return df

    def plot_maiores_favorecidos(self, df, n_favorecido):
        """
        Gráfico de barras mostrando os maiores favorecidos dos empenhos.
        """
        df['EMP_VALOR_CONVERTIDO'] = pd.to_numeric(df['EMP_VALOR_CONVERTIDO'], errors='coerce')
        favorecidos_df = df.groupby('FAV_NOME')['EMP_VALOR_CONVERTIDO'].sum().reset_index()
        favorecidos_df = favorecidos_df.nlargest(n_favorecido, 'EMP_VALOR_CONVERTIDO')
        fig = px.bar(favorecidos_df, x='FAV_NOME', y='EMP_VALOR_CONVERTIDO', 
                     title=f"Top {n_favorecido} Favorecidos pelos Empenhos",
                     labels={"FAV_NOME": "Favorecido", "EMP_VALOR_CONVERTIDO": "Valor Empenhado (R$)"})
        fig.update_layout(xaxis_title="Favorecido", yaxis_title="Valor Empenhado (R$)")
        return fig

    def plot_categorias(self, df):
        """
        Gráfico de barras mostrando a distribuição dos valores empenhados por categoria de despesa.
        """
        categoria_df = df.groupby('CDE_NOME')['EMP_VALOR_CONVERTIDO'].sum().reset_index()
        fig = px.bar(categoria_df, x='CDE_NOME', y='EMP_VALOR_CONVERTIDO', 
                     title="Distribuição dos Empenhos por Categoria de Despesa",
                     labels={"CDE_NOME": "Categoria de Despesa", "EMP_VALOR_CONVERTIDO": "Valor Empenhado (R$)"})
        fig.update_layout(xaxis_title="Categoria de Despesa", yaxis_title="Valor Empenhado (R$)")
        return fig

    def plot_comparacao_orgaos(self, df, n_orgao):
        """
        Gráfico de barras comparando os valores empenhados por órgãos governamentais,
        limitando o número de órgãos a serem exibidos com base na seleção do usuário.
        """
        orgaos_df = df.groupby('ORG_NOME')['EMP_VALOR_CONVERTIDO'].sum().reset_index()
        orgaos_df = orgaos_df.nlargest(n_orgao, 'EMP_VALOR_CONVERTIDO')
        fig = px.bar(orgaos_df, x='ORG_NOME', y='EMP_VALOR_CONVERTIDO', 
                    title=f"Comparação dos {n_orgao} maiores Empenhos por Órgãos Governamentais",
                    labels={"ORG_NOME": "Órgão Governamental", "EMP_VALOR_CONVERTIDO": "Valor Empenhado (R$)"})
        fig.update_layout(xaxis_title="Órgão Governamental", yaxis_title="Valor Empenhado (R$)")
        return fig

    def plot_evolucao_empenhos(self, df):
        """
        Gráfico de linha mostrando a evolução dos valores empenhados ao longo do período selecionado.
        """
        empenhos_df = df.groupby('EMP_DATA_EMISSAO')['EMP_VALOR_CONVERTIDO'].sum().reset_index()
        fig = px.line(empenhos_df, x='EMP_DATA_EMISSAO', y='EMP_VALOR_CONVERTIDO', 
                      title="Evolução dos Empenhos ao Longo do Tempo",
                      labels={"EMP_DATA_EMISSAO": "Data de Emissão", "EMP_VALOR_CONVERTIDO": "Valor Empenhado (R$)"})
        fig.update_layout(xaxis_title="Data de Emissão", yaxis_title="Valor Empenhado (R$)")
        return fig

    def gerar_dashboard(self):
        """
        Método que organiza os gráficos no layout do dashboard.
        """
        app = Dash(__name__)

        # Gerar a lista de opções do dropdown para órgãos
        dropdown_options_orgaos = [{'label': f'{i} primeiros órgãos', 'value': i} for i in range(1, 11)]
        dropdown_options_orgaos += [{'label': f'{i} primeiros órgãos', 'value': i} for i in range(20, 60, 10)]
        
        # Gerar a lista de opções do dropdown para favorecidos
        dropdown_options_favorecidos = [{'label': f'{i} primeiros favorecidos', 'value': i} for i in range(1, 11)]
        dropdown_options_favorecidos += [{'label': f'{i} primeiros favorecidos', 'value': i} for i in range(20, 60, 10)]

        app.layout = html.Div(children=[

            html.H1(children='Dashboard de Análise dos Empenhos do Governo Federal', style={'text-align': 'center'}),

            dcc.DatePickerRange(
                id='date-picker-range',
                start_date='2024-01-01',
                end_date='2024-01-31',
                display_format='DD/MM/YYYY',
                start_date_placeholder_text='Data Inicial',
                end_date_placeholder_text='Data Final'
            ),

            html.Div(id='output-container-date-picker-range', style={'margin-top': '20px', 'text-align': 'center'}),

            html.Div([
                html.H3("Total de Empenho no Período", style={'text-align': 'center'}),
                html.Div(id='total-empenho-card', 
                         style={
                             'display': 'flex', 
                             'justify-content': 'center', 
                             'align-items': 'center', 
                             'height': '100px', 
                             'background-color': '#f5f5f5', 
                             'border-radius': '10px', 
                             'width': '100%', 
                             'font-size': '24px', 
                             'font-weight': 'bold',
                             'color': '#2c3e50'
                         })
            ], style={'margin-top': '20px', 'margin-bottom': '20px'}),

            html.Div([  
                html.Label('Quantidade de favorecidos a serem exibidos:'),
                dcc.Dropdown(
                    id='favorecido-dropdown',
                    options=dropdown_options_favorecidos,
                    value=10,
                    clearable=False,
                    style={'width': '40%'}
                )
            ], style={'text-align': 'left', 'margin-bottom': '20px'}),

            html.Div([
                dcc.Graph(id='grafico-categorias', style={'width': '48%', 'display': 'inline-block'}),
                dcc.Graph(id='grafico-favorecidos', style={'width': '48%', 'display': 'inline-block'}),
            ], style={'display': 'flex', 'justify-content': 'center', 'flex-wrap': 'wrap', 'margin-top': '20px'}),

            html.Div([
                html.Label('Quantidade de órgãos a serem exibidos:'),
                dcc.Dropdown(
                    id='orgao-dropdown',
                    options=dropdown_options_orgaos,
                    value=10,
                    clearable=False,
                    style={'width': '40%'}
                )
            ], style={'text-align': 'left', 'margin-bottom': '20px'}),

            html.Div([
                dcc.Graph(id='grafico-orgaos', style={'width': '48%', 'display': 'inline-block'}),
                dcc.Graph(id='grafico-evolucao', style={'width': '48%', 'display': 'inline-block'}),
            ], style={'display': 'flex', 'justify-content': 'center', 'flex-wrap': 'wrap', 'margin-top': '20px'}),
        ])

        @app.callback(
            [
                Output('total-empenho-card', 'children'),
                Output('grafico-categorias', 'figure'),
                Output('grafico-favorecidos', 'figure'),
                Output('grafico-orgaos', 'figure'),
                Output('grafico-evolucao', 'figure'),
            ],
            [
                Input('date-picker-range', 'start_date'),
                Input('date-picker-range', 'end_date'),
                Input('favorecido-dropdown', 'value'),
                Input('orgao-dropdown', 'value'),
            ]
        )
        def atualizar_dashboard(start_date, end_date, n_favorecido, n_orgao):
            df = self.get_data(start_date, end_date)

            total_empenho = df['EMP_VALOR_CONVERTIDO'].sum()
            total_empenho_formatado = f"R$ {total_empenho:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

            fig_categorias = self.plot_categorias(df)
            fig_favorecidos = self.plot_maiores_favorecidos(df, n_favorecido)
            fig_orgaos = self.plot_comparacao_orgaos(df, n_orgao)
            fig_evolucao = self.plot_evolucao_empenhos(df)

            return total_empenho_formatado, fig_categorias, fig_favorecidos, fig_orgaos, fig_evolucao

        return app

if __name__ == '__main__':
    connection = create_connection()

    dashboard = EmpenhosDashboard(connection)

    app = dashboard.gerar_dashboard()
    app.run_server(debug=True)
