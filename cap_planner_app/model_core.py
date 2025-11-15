
import pandas as pd
import numpy as np
import pulp
from pathlib import Path

DATA_DIR = Path(__file__).parent / 'data'
LINE_PREFIX = 'Production Line'

def load_baseline():
    rates = pd.read_csv(DATA_DIR / 'rates.csv')
    calendar = pd.read_csv(DATA_DIR / 'calendar.csv')
    demand = pd.read_csv(DATA_DIR / 'demand.csv')
    lines = [c for c in rates.columns if str(c).startswith(LINE_PREFIX)]
    for c in lines:
        rates[c] = pd.to_numeric(rates[c], errors='coerce')
    calendar['Operating_Days'] = pd.to_numeric(calendar['Operating_Days'], errors='coerce')
    for c in demand.columns:
        if c != 'PRODUCT':
            demand[c] = pd.to_numeric(demand[c], errors='coerce').fillna(0.0)
    return rates, calendar, demand

def demand_wide_to_long(demand_wide: pd.DataFrame) -> pd.DataFrame:
    month_cols = [c for c in demand_wide.columns if c != 'PRODUCT']
    return demand_wide.melt(id_vars='PRODUCT', value_vars=month_cols, var_name='Month', value_name='Demand_MT')

def compute_allocation(demand_wide: pd.DataFrame = None, rates_df: pd.DataFrame = None, calendar_df: pd.DataFrame = None):
    if rates_df is None or calendar_df is None or demand_wide is None:
        rates0, cal0, dem0 = load_baseline()
        rates_df = rates_df if rates_df is not None else rates0
        calendar_df = calendar_df if calendar_df is not None else cal0
        demand_wide = demand_wide if demand_wide is not None else dem0

    products = rates_df['PRODUCT'].tolist()
    lines = [c for c in rates_df.columns if str(c).startswith(LINE_PREFIX)]
    months = calendar_df['Month'].tolist()

    cap_pl = rates_df.set_index('PRODUCT')[lines]
    oper_days = calendar_df.set_index('Month')['Operating_Days']

    demand_long = demand_wide_to_long(demand_wide)
    Demand = demand_long.pivot_table(index='PRODUCT', columns='Month', values='Demand_MT', aggfunc='sum').reindex(products).reindex(columns=months).fillna(0)

    solutions = {}
    util_rows = []

    for m in months:
        prob = pulp.LpProblem('Alloc_' + str(m), pulp.LpMaximize)
        x = {}
        for p in products:
            for l in lines:
                x[(p,l)] = pulp.LpVariable('x_' + str(p).replace(' ','_') + '_' + l.split()[-1] + '_' + str(m), lowBound=0)
        prob += pulp.lpSum([x[(p,l)] for p in products for l in lines])
        for l in lines:
            prob += pulp.lpSum([x[(p,l)] for p in products]) <= float(cap_pl[l].sum()) * float(oper_days.loc[m])
        for p in products:
            dem_val = float(Demand.loc[p, m]) if (p in Demand.index and m in Demand.columns) else 0.0
            prob += pulp.lpSum([x[(p,l)] for l in lines]) <= dem_val
        prob.solve(pulp.PULP_CBC_CMD(msg=False))
        rows = []
        for p in products:
            for l in lines:
                val = x[(p,l)].value() or 0.0
                if val > 0:
                    rows.append({'Month': m, 'PRODUCT': p, 'Line': l, 'MT': val})
        solutions[m] = pd.DataFrame(rows)
        for l in lines:
            produced = sum((x[(p,l)].value() or 0.0) for p in products)
            cap_month = float(cap_pl[l].sum()) * float(oper_days.loc[m])
            util = produced / cap_month if cap_month > 0 else 0.0
            util_rows.append({'Month': m, 'Line': l, 'MT': produced, 'Capacity_MT': cap_month, 'Utilization': util})

    allocations_all = pd.concat(solutions.values(), ignore_index=True) if len(solutions) else pd.DataFrame(columns=['Month','PRODUCT','Line','MT'])
    util_df = pd.DataFrame(util_rows)

    produced_pm = allocations_all.groupby(['Month','PRODUCT'])['MT'].sum().reset_index()
    demand_pm = demand_long.groupby(['Month','PRODUCT'])['Demand_MT'].sum().reset_index()
    fill_rates_pm = pd.merge(demand_pm, produced_pm, on=['Month','PRODUCT'], how='left').fillna({'MT':0})
    def _fr(r):
        return (r['MT'] / r['Demand_MT']) if (r['Demand_MT'] and r['Demand_MT'] > 0) else None
    fill_rates_pm['Fill_Rate'] = fill_rates_pm.apply(_fr, axis=1)
    return allocations_all, util_df, fill_rates_pm, {'products': products, 'lines': lines, 'months': months}
