import pandas as pd
import plotly.graph_objs as go
from dash import Dash, dcc, html, Input, Output

# === 读取数据 ===
df_brokers = pd.read_excel(r'经纪商净持仓_已修正.xlsx', sheet_name="每周数据")
df_cftc = pd.read_excel(r"CFTC.xlsx", sheet_name="合并")

# 预处理
df_brokers['日期'] = pd.to_datetime(df_brokers['日期'])
df_cftc['ReportDateAsYyyyMmDd'] = pd.to_datetime(df_cftc['ReportDateAsYyyyMmDd'])


# === 修改部分：将空头持仓改为绝对值 ===
# 先保存原始净持仓值
df_brokers['原始净持仓'] = df_brokers['净持仓']
# 对空头持仓取绝对值
df_brokers['总空头持仓'] = df_brokers['总空头持仓'].abs()
# 重新计算净持仓（保持原值不变）
df_brokers['净持仓'] = df_brokers['原始净持仓']
# 删除临时列
del df_brokers['原始净持仓']


# CFTC 字段映射
cftc_map = {
    'Managed Money': {
        'long': 'MMoneyPositionsLongAll',
        'short': 'MMoneyPositionsShortAll',
        'net': 'MMNetPosition',
        'long_pct': 'MMPL%',
        'short_pct': 'MMPS%',
        'net_pct': 'MMNet%'
    },
    'Noncommercial': {
        'long': 'NonCommPositionsLongAll',
        'short': 'NonCommPositionsShortAll',
        'net': 'NonCommNetPosition',
        'long_pct': 'NonCommPL%',
        'short_pct': 'NonCommPS%',
        'net_pct': 'NonCommNet%'
    }
}

# 经纪商字段映射
title_to_col = {
    '总多头持仓': '总多头持仓',
    '总多头持仓变化率': '总多头持仓周变化率',
    '总空头持仓': '总空头持仓',
    '总空头持仓变化率': '总空头持仓周变化率',
    '净持仓': '净持仓',
    '净持仓变化率': '净持仓周变化率'
}

# 图表字段和显示名
charts = [
    ('总多头持仓', 'long'),
    ('总多头持仓变化率', 'long_pct'),
    ('总空头持仓', 'short'),
    ('总空头持仓变化率', 'short_pct'),
    ('净持仓', 'net'),
    ('净持仓变化率', 'net_pct')
]

# 固定颜色
color_map = {
    '摩根大通': 'blue',
    '乾坤期货': 'red',
    'Managed Money': 'green',
    'Noncommercial': 'orange'
}

app = Dash(__name__)

app.layout = html.Div([
    html.H2("摩根大通、乾坤期货与 CFTC 持仓对比", style={'textAlign': 'center'}),
    html.Div([
        html.Label("选择年份"),
        dcc.Dropdown(
            id='year-dropdown',
            options=[{'label': str(y), 'value': y} for y in sorted(df_brokers['日期'].dt.year.unique())],
            multi=True,
            placeholder="请选择年份"
        ),
    ], style={'width': '20%', 'display': 'inline-block', 'marginRight': '30px'}),

    html.Div([
        html.Label("选择经纪商"),
        dcc.Dropdown(
            id='broker-dropdown',
            options=[{'label': b, 'value': b} for b in df_brokers['经纪商名称'].unique()],
            multi=True,
            placeholder="可多选，留空不显示"
        ),
    ], style={'width': '25%', 'display': 'inline-block', 'marginRight': '30px'}),

    html.Div([
        html.Label("选择CFTC分类"),
        dcc.Dropdown(
            id='cftc-category-dropdown',
            options=[{'label': c, 'value': c} for c in cftc_map.keys()],
            multi=True,
            placeholder="可多选，留空不显示"
        ),
    ], style={'width': '25%', 'display': 'inline-block'}),

    html.Div([
        html.Label("移动平均窗口（变化率图表必选）"),
        dcc.RadioItems(
            id='avg-window',
            options=[
                {'label': '1天', 'value': 1},
                {'label': '7天', 'value': 7},
                {'label': '30天', 'value': 30}
            ],
            value=7,
            labelStyle={'display': 'inline-block', 'marginRight': '15px'}
        ),
    ], style={'marginTop': '20px', 'width': '90%', 'textAlign': 'center'}),

    html.Div(id='graphs-container', style={'marginTop': '30px'})
])

@app.callback(
    Output('graphs-container', 'children'),
    Input('year-dropdown', 'value'),
    Input('broker-dropdown', 'value'),
    Input('cftc-category-dropdown', 'value'),
    Input('avg-window', 'value')
)
def update_graphs(selected_years, selected_brokers, selected_cftc, avg_window):
    if not selected_years:
        return [html.Div("请至少选择一个年份", style={'color':'red', 'textAlign':'center', 'marginTop': '30px'})]

    children = []

    df_b = df_brokers[df_brokers['日期'].dt.year.isin(selected_years)]
    df_c = df_cftc[df_cftc['ReportDateAsYyyyMmDd'].dt.year.isin(selected_years)]

    for display_name, cftc_key in charts:
        fig = go.Figure()
        col_broker = title_to_col[display_name]

        # 经纪商数据曲线
        if selected_brokers:
            for broker in selected_brokers:
                if col_broker not in df_b.columns:
                    continue
                df_sub = df_b[df_b['经纪商名称'] == broker][['日期', col_broker]].copy()
                y = df_sub[col_broker]

                # 变化率图必须做移动平均（列名含“变化率”）
                if "变化率" in display_name:
                    y = y.rolling(avg_window, min_periods=1).mean()

                fig.add_trace(go.Scatter(
                    x=df_sub['日期'],
                    y=y,
                    mode='lines+markers',
                    name=broker,
                    line=dict(color=color_map.get(broker, None))
                ))

        # CFTC数据曲线
        if selected_cftc:
            for cftc_cat in selected_cftc:
                if cftc_cat not in cftc_map:
                    continue
                cftc_col = cftc_map[cftc_cat][cftc_key]
                if cftc_col not in df_c.columns:
                    continue
                df_sub = df_c[['ReportDateAsYyyyMmDd', cftc_col]].copy()
                y = df_sub[cftc_col]
                # 变化率图必须做移动平均
                if "变化率" in display_name:
                    y = y.rolling(avg_window, min_periods=1).mean()
                fig.add_trace(go.Scatter(
                    x=df_sub['ReportDateAsYyyyMmDd'],
                    y=y,
                    mode='lines+markers',
                    name=f'CFTC {cftc_cat}',
                    line=dict(color=color_map.get(cftc_cat, None), dash='dash')
                ))

        fig.update_layout(
            title=display_name,
            height=350,
            margin=dict(l=20, r=20, t=40, b=20),
            legend_title="来源"
        )

        children.append(html.Div(dcc.Graph(figure=fig), style={'marginBottom': '40px', 'width': '90%', 'margin': 'auto'}))

    return children

app = Dash(__name__)  # 这是Dash应用的初始化
server = app.server  # 这行加在`app = Dash(__name__)`之后

if __name__ == '__main__':
    app.run(debug=True)
