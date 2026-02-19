"""Script para generar CSVs de ejemplo con datos 2024-2026."""
import csv
import random
import os
import tempfile
from datetime import datetime, timedelta

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

def safe_write(filename, write_fn):
    """Write to file, handling locks by writing to temp then replacing."""
    path = os.path.join(OUT_DIR, filename)
    try:
        with open(path, 'w', newline='', encoding='utf-8') as f:
            write_fn(f)
    except PermissionError:
        tmp = path + '.tmp'
        with open(tmp, 'w', newline='', encoding='utf-8') as f:
            write_fn(f)
        try:
            os.replace(tmp, path)
        except PermissionError:
            print(f"  AVISO: {filename} está bloqueado. Guardado como {filename}.tmp")
            return
    print(f"  {filename} guardado")

random.seed(42)

productos = [
    ('P001', 'Laptop HP ProBook 450', 'Electrónica', 12500.00),
    ('P002', 'Monitor Dell 27 pulgadas', 'Electrónica', 5800.00),
    ('P003', 'Teclado Logitech MX Keys', 'Periféricos', 2100.00),
    ('P004', 'Mouse Logitech MX Master', 'Periféricos', 1650.00),
    ('P005', 'Auriculares Sony WH-1000XM5', 'Audio', 6500.00),
    ('P006', 'Webcam Logitech C920', 'Periféricos', 1800.00),
    ('P007', 'Disco SSD Samsung 1TB', 'Almacenamiento', 2200.00),
    ('P008', 'Memoria RAM 16GB DDR4', 'Componentes', 1400.00),
    ('P009', 'Cable HDMI 2m', 'Accesorios', 180.00),
    ('P010', 'Hub USB-C 7 puertos', 'Accesorios', 850.00),
    ('P011', 'Silla Ergonómica Premium', 'Mobiliario', 8500.00),
    ('P012', 'Escritorio Ajustable', 'Mobiliario', 12000.00),
    ('P013', 'Impresora HP LaserJet', 'Impresión', 4500.00),
    ('P014', 'Toner HP 26A', 'Consumibles', 950.00),
    ('P015', 'UPS APC 1500VA', 'Energía', 3800.00),
    ('P016', 'Router WiFi 6', 'Redes', 2800.00),
    ('P017', 'Switch 24 puertos', 'Redes', 4200.00),
    ('P018', 'Tablet Samsung Galaxy Tab', 'Electrónica', 7200.00),
    ('P019', 'Cargador Universal 65W', 'Accesorios', 650.00),
    ('P020', 'Mochila para Laptop', 'Accesorios', 1200.00),
]

clientes_list = [
    ('C001', 'TechSolutions SA de CV'), ('C002', 'Grupo Industrial Norte'),
    ('C003', 'Consultores Asociados'), ('C004', 'Farmacia del Centro'),
    ('C005', 'Restaurant La Hacienda'), ('C006', 'Despacho Legal Torres'),
    ('C007', 'Constructora Moderna'), ('C008', 'Escuela Primaria Juárez'),
    ('C009', 'Clínica San Rafael'), ('C010', 'Taller Mecánico López'),
    ('C011', 'Papelería El Estudiante'), ('C012', 'Hotel Vista Hermosa'),
    ('C013', 'Agencia de Viajes Sol'), ('C014', 'Gimnasio FitLife'),
    ('C015', 'Veterinaria Animal Care'),
]

proveedores = [
    ('PRV001', 'Telmex'), ('PRV002', 'CFE'), ('PRV003', 'Office Depot'),
    ('PRV004', 'Google Ads'), ('PRV005', 'DHL Express'), ('PRV006', 'Seguros Atlas'),
    ('PRV007', 'Inmobiliaria Centro'), ('PRV008', 'Agua y Drenaje'),
    ('PRV009', 'Capacita MX'), ('PRV010', 'Microsoft'),
    ('PRV011', 'Amazon AWS'), ('PRV012', 'Papelera Nacional'),
]

start = datetime(2024, 1, 1)
end = datetime(2026, 2, 17)


# ===================== VENTAS =====================
print("Generando ventas...")
rows = []
current = start
while current <= end:
    n = random.randint(2, 6) if current.weekday() < 5 else random.randint(0, 2)
    for _ in range(n):
        prod = random.choice(productos)
        cli = random.choice(clientes_list)
        cant = random.randint(1, 10)
        precio = round(prod[3] * random.uniform(0.95, 1.05), 2)
        total = round(cant * precio, 2)
        rows.append([
            current.strftime('%Y-%m-%d'), prod[0], prod[1],
            cant, precio, total, cli[0], prod[2]
        ])
    current += timedelta(days=1)

def write_ventas(f):
    w = csv.writer(f)
    w.writerow(['fecha', 'producto_id', 'nombre_producto', 'cantidad',
                'precio_unitario', 'monto_total', 'cliente_id', 'categoria'])
    w.writerows(rows)
safe_write('ventas_ejemplo.csv', write_ventas)
print(f"  {len(rows)} registros")


# ===================== GASTOS =====================
print("Generando gastos...")
random.seed(43)
categorias_gasto = [
    'Nómina', 'Renta', 'Servicios', 'Material oficina', 'Marketing',
    'Logística', 'Mantenimiento', 'Seguros', 'Capacitación', 'Software'
]
tipos_pago = ['Transferencia', 'Tarjeta crédito', 'Efectivo', 'Cheque']
descripciones = {
    'Nómina': ['Pago nómina quincenal', 'Pago aguinaldo', 'Bonos trimestrales', 'Horas extra'],
    'Renta': ['Renta oficina principal', 'Renta bodega almacén'],
    'Servicios': ['Servicio de internet', 'Electricidad', 'Agua', 'Telefonía', 'Gas'],
    'Material oficina': ['Papelería general', 'Toner impresora', 'Carpetas y folders', 'Artículos limpieza'],
    'Marketing': ['Campaña Google Ads', 'Publicidad redes sociales', 'Diseño flyers', 'Evento promocional'],
    'Logística': ['Envío paquetería', 'Combustible flotilla', 'Mantenimiento vehículos'],
    'Mantenimiento': ['Mantenimiento equipo cómputo', 'Reparación aire acondicionado', 'Limpieza oficinas'],
    'Seguros': ['Seguro contra incendio', 'Seguro responsabilidad civil', 'Seguro equipo electrónico'],
    'Capacitación': ['Curso Excel avanzado', 'Taller liderazgo', 'Certificación profesional'],
    'Software': ['Licencia Microsoft 365', 'Suscripción AWS', 'Licencia antivirus', 'Suscripción Zoom'],
}

rows_g = []
current = start
factura_num = 1000
while current <= end:
    n = random.randint(1, 4) if current.weekday() < 5 else random.randint(0, 1)
    for _ in range(n):
        cat = random.choice(categorias_gasto)
        desc = random.choice(descripciones[cat])
        prov = random.choice(proveedores)
        if cat == 'Nómina':
            monto = round(random.uniform(5000, 35000), 2)
        elif cat == 'Renta':
            monto = round(random.uniform(8000, 25000), 2)
        else:
            monto = round(random.uniform(100, 8000), 2)
        tp = random.choice(tipos_pago)
        factura_num += 1
        rows_g.append([
            current.strftime('%Y-%m-%d'), desc, cat, monto,
            prov[0], prov[1], tp, f'F-{factura_num}', ''
        ])
    current += timedelta(days=1)

def write_gastos(f):
    w = csv.writer(f)
    w.writerow(['fecha', 'descripcion', 'categoria', 'monto', 'proveedor_id',
                'nombre_proveedor', 'tipo_pago', 'numero_factura', 'notas'])
    w.writerows(rows_g)
safe_write('gastos_ejemplo.csv', write_gastos)
print(f"  {len(rows_g)} registros")


# ===================== INVENTARIO =====================
print("Generando inventario...")
rows_i = []
ubicaciones = ['Bodega A', 'Bodega B', 'Estante 1', 'Estante 2', 'Vitrina', 'Almacén principal']
for prod in productos:
    cant_actual = random.randint(5, 200)
    cant_min = random.randint(3, 20)
    precio_compra = round(prod[3] * 0.65, 2)
    prov = random.choice(proveedores)
    rows_i.append([
        prod[0], prod[1], cant_actual,
        f'Producto de {prod[2].lower()}', prod[2],
        cant_min, 'pieza', precio_compra, prod[3],
        prov[0], random.choice(ubicaciones)
    ])

def write_inventario(f):
    w = csv.writer(f)
    w.writerow(['producto_id', 'nombre_producto', 'cantidad_actual', 'descripcion',
                'categoria', 'cantidad_minima', 'unidad_medida', 'precio_compra',
                'precio_venta', 'proveedor_id', 'ubicacion'])
    w.writerows(rows_i)
safe_write('inventario_ejemplo.csv', write_inventario)
print(f"  {len(rows_i)} registros")


# ===================== CLIENTES =====================
print("Generando clientes...")
random.seed(44)
ciudades = ['Monterrey', 'Guadalajara', 'CDMX', 'Puebla', 'Querétaro', 'Mérida', 'Tijuana', 'León']
tipos_cliente = ['Mayorista', 'Minorista', 'Corporativo', 'Gobierno', 'Educación']
calles = ['Constitución', 'Revolución', 'Juárez', 'Hidalgo', 'Reforma',
          'Morelos', 'Allende', 'Madero', 'Guerrero', 'Zaragoza']

all_clients = list(clientes_list) + [
    ('C016', 'Ferretería El Martillo'), ('C017', 'Librería Cervantes'),
    ('C018', 'Panadería La Espiga'), ('C019', 'Auto Partes Express'),
    ('C020', 'Centro Dental Smile'), ('C021', 'Floristería Primavera'),
    ('C022', 'Estética Glamour'), ('C023', 'Tintorería Express'),
    ('C024', 'Joyería Diamante'), ('C025', 'Óptica Visual'),
    ('C026', 'Zapatería El Paso'), ('C027', 'Mueblería del Valle'),
    ('C028', 'Refaccionaria Total'), ('C029', 'Laboratorio Clínico Plus'),
    ('C030', 'Cervecería Artesanal Norte'),
]

rows_c = []
for cid, nombre in all_clients:
    ciudad = random.choice(ciudades)
    fecha_reg = (start + timedelta(days=random.randint(0, 700))).strftime('%Y-%m-%d')
    domain = nombre.split()[0].lower().replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
    email = f'contacto@{domain}.com.mx'
    tel = f'81{random.randint(10000000, 99999999)}'
    direccion = f'Av. {random.choice(calles)} #{random.randint(100, 9999)}'
    cp = str(random.randint(10000, 99999))
    rfc_prefix = nombre[:3].upper().replace(' ', 'X')
    rfc = f'{rfc_prefix}{random.randint(100000, 999999)}XX{random.randint(0, 9)}'
    tipo = random.choice(tipos_cliente)
    activo = 'true' if random.random() > 0.1 else 'false'
    rows_c.append([cid, nombre, fecha_reg, email, tel, direccion, ciudad, cp, rfc, tipo, '', activo])

def write_clientes(f):
    w = csv.writer(f)
    w.writerow(['cliente_id', 'nombre', 'fecha_registro', 'email', 'telefono',
                'direccion', 'ciudad', 'codigo_postal', 'rfc', 'tipo_cliente', 'notas', 'activo'])
    w.writerows(rows_c)
safe_write('clientes_ejemplo.csv', write_clientes)
print(f"  {len(rows_c)} registros")

print(f"\nTodos los archivos generados en {OUT_DIR}")
