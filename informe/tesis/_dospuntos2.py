import sys

def aplicar(archivo, pares):
    t = open(archivo, encoding="utf-8").read()
    for viejo, nuevo in pares:
        if viejo not in t:
            sys.exit(f"NO ENCONTRADO en {archivo}: {viejo}")
        t = t.replace(viejo, nuevo, 1)
    open(archivo, "w", encoding="utf-8").write(t)
    print(archivo, len(pares))

aplicar("e1_parte1.tex", [
("\\subsection{Por qué pasa: cinco porqués}",
 "\\subsection{\\texorpdfstring{\\segun{Por qué pasa: cinco porqués}{Por qué pasa, en cinco porqués}}{Por qué pasa, en cinco porqués}}"),
("\\emph{línea de pedido}: un producto", "\\emph{línea de pedido}\\segun{: }{, es decir, }un producto"),
("\\textbf{cobertura}: se prefiere", "\\textbf{cobertura}\\segun{: }{, ya que }se prefiere"),
("huecos intermedios}: semanas", "huecos intermedios}\\segun{: }{, es decir, }semanas"),
])
aplicar("e1_parte2.tex", [
("{corresponde al proveedor:}", "{corresponde al proveedor, ya que}"),
])
