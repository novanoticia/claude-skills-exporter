# repo-byte-nulo

Banco de pruebas: un byte nulo no puede sacar a un fichero de texto del motor.

`skills/byte-nulo/scripts/run.sh` es un script de shell corriente con un byte
nulo metido en un comentario. Antes, `es_binario` lo daba por binario y
`patrones.analizar` lo saltaba entero, asi que su carga quedaba invisible.

`bin/de-verdad.bin` es un binario de verdad, con cabecera ELF. Esta aqui para
lo contrario: comprobar que el hallazgo nuevo NO se dispara sobre un fichero
que si es binario. Se menciona en este README a proposito, para que tampoco
dispare SEC-BINARIO-NO-DOCUMENTADO-001 y el fixture mida solo una cosa.
