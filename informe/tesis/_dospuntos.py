import sys

def segun(archivo, pares):
    t = open(archivo, encoding="utf-8").read()
    for viejo, nuevo in pares:
        n = t.count(viejo)
        if n == 0:
            sys.exit(f"NO ENCONTRADO en {archivo}: {viejo}")
        t = t.replace(viejo, "\\segun{" + viejo + "}{" + nuevo + "}", 1)
    open(archivo, "w", encoding="utf-8").write(t)
    print(archivo, len(pares))

segun("e1_parte1.tex", [
("nadie verifica: que", "nadie verifica, que"),
("con estas palabras: «", "con estas palabras, «"),
("originó la revisión: advierte", "originó la revisión y advierte"),
("conjunto de datos real: el archivo", "conjunto de datos real, el archivo"),
("No son pedidos adicionales: son pedidos", "No son pedidos adicionales, sino pedidos"),
("ningún modelo: alcanza con", "ningún modelo, ya que alcanza con"),
("Tienda ATE, pan grande: pedido real", "Tienda ATE, pan grande. Pedido real"),
("propio despacho: se produce", "propio despacho, porque se produce"),
("puede responder: si la tienda", "puede responder, que es si la tienda"),
("ventaja sobre preguntar: el método", "ventaja sobre preguntar, ya que el método"),
("Responsable del resultado:", "Responsable del resultado."),
("de principio a fin: la preparación", "de principio a fin, incluida la preparación"),
("no reemplaza la decisión: para cada", "no reemplaza la decisión, ya que para cada"),
("no aprende nada: dentro de un año", "no aprende nada, y dentro de un año"),
("decirle por qué: según sus", "decirle por qué, por ejemplo, según sus"),
("operadas por NGR y EyH: tres productos", "operadas por NGR y EyH, con tres productos"),
("contra hechos conocidos: el caso", "contra hechos conocidos, como el caso"),
("más elaborada: el pedido de la semana anterior", "más elaborada. La primera es el pedido de la semana anterior"),
("si se pasa por alto: el historial", "si se pasa por alto, y es que el historial"),
("el área ya reconoce: duplicidad", "el área ya reconoce, como la duplicidad"),
("hay que decirlo: que el problema", "hay que decirlo. Que el problema"),
("puede costar más: la tienda", "puede costar más, porque la tienda"),
("un error: puede ser", "un error, ya que puede ser"),
("simple posible: ", "simple posible, ya que "),
("sin salir del programa: el gráfico", "sin salir del programa, como el gráfico"),
("más allá del orden: cada semana", "más allá del orden, ya que cada semana"),
("de manera deliberada: decidir", "de manera deliberada, porque decidir"),
("buscaba evitar: la venta", "buscaba evitar, ya que la venta"),
("en su favor: ante la duda", "en su favor, y ante la duda"),
("análisis de datos: no requiere", "análisis de datos, y no requiere"),
])

segun("e1_parte2.tex", [
("delimitar mejor el problema: que el pedido", "delimitar mejor el problema, de modo que el pedido"),
("Hay que rehacerlo: otro ERP", "Hay que rehacerlo, con otro ERP"),
("Funciona igual: el dato", "Funciona igual, porque el dato"),
("no se acumula: el pedido", "no se acumula, porque el pedido"),
("traslado de responsabilidad: hoy,", "traslado de responsabilidad. Hoy,"),
("le da contenido: en lugar", "le da contenido, ya que en lugar"),
("ausencia de pedido: una tienda", "ausencia de pedido, es decir, una tienda"),
])
