## SQL
- Adicionei o sql_schema.yaml com contexto das tabelas SQL (semântica, joins, filtros e padrões de query), para apoiar geração de queries mais corretas.

- Integrei esse schema na SQL tool, para orientar a geração de queries com base no contexto real dos dados.

## MongoDB
- Criei um catálogo para Mongo (mongo_catalog.yaml) com collections disponíveis, finalidade, campos pesquisáveis e notas de utilização (WHO GHO + MedlinePlus).

- Mongo tool passa a carregar o catálogo antes de gerar resposta.

## RAG 
- Criei um inventário do corpus RAG (rag_corpus.yaml) com fontes, estratégia de chunking, modelos de embedding/reranker, metadados, pontos fortes e limitações.

- Mantive o rag_tool.py sem alterações, por ser apenas uma camada de orquestração (wrapper), evitando mudanças desnecessárias. Adicionei o contexto na pipeline de geração de resposta, para que o modelo tenha acesso ao conhecimento do corpus durante a geração.