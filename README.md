# Radar Praia Grande

O que cada vereador de Praia Grande-SP faz, só com dados oficiais da Câmara Municipal: presença nas sessões, propostas apresentadas, como votou e o que foi pedido para cada bairro.

**Site:** https://victorsfila.github.io/radar-praia-grande/

Projeto independente, sem ligação com a Câmara, a Prefeitura ou partidos. Montado a partir do manual "Como criar o Radar da sua cidade", de Gabriel Damasceno.

## De onde vêm os dados

Todos os números vêm do sistema público de consulta da Câmara Municipal da Estância Balneária de Praia Grande:
https://www.praiagrande.sp.leg.br/dispositivo/ideCustom/camarapg_publico/

- vereadores da legislatura 2025–2028;
- todas as propostas apresentadas em 2025 e 2026 (indicações, requerimentos, projetos, moções…);
- listas de presença de cada sessão;
- votações nominais (voto de cada vereador).

## Regras

- Só dado oficial. Cada número do site tem link para a fonte na Câmara.
- Mesma régua para todos os vereadores, de todos os partidos.
- Dado ausente não é falta: sessões sem lista de presença publicada não contam para ninguém.
- O que é estimativa está escrito como estimativa (por exemplo, o endereço e o tema dos pedidos, lidos automaticamente da ementa).
- Só contato institucional. Telefones não são publicados.

As regras completas estão na página "Sobre" do site.

## Como funciona

```
coletor/coleta.py    baixa os dados do sistema da Câmara (devagar, com pausa entre páginas)
coletor/conferir.py  recusa a coleta se ela vier incompleta ou estranha
coletor/build.py     transforma os dados nos arquivos do site (site/dados/)
coletor/classificar.py  regra única que separa as propostas em grupos
coletor/enderecos.py    lê rua, bairro e tema de cada pedido
site/                o site (uma página só, sem servidor)
```

O robô (`.github/workflows/atualizar.yml`) roda toda madrugada às 03:17 (horário de Brasília). Se a coleta vier incompleta, ele não publica, e o site fica com a última versão boa. Para rodar na hora: aba **Actions** → **Atualizar dados** → **Run workflow**.

## Encontrou um erro?

Abra um aviso em **Issues** com o link da página do Radar e o dado oficial correto.
