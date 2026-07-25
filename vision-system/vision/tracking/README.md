# tracking/

**Productor.** Mantiene la identidad de cada objeto entre cuadros y arma el
estado del mundo inmutable. Ante oclusión conserva la última posición con la
edad creciendo; nunca hace parpadear un objeto entre existir y no existir.
