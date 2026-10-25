# SCQL - Sistema de Captação e Qualificação de Leads

Protótipo de sistema de informação desenvolvido para o Projeto Integrado
Individual do curso de Análise e Desenvolvimento de Sistemas.

O sistema apoia o processo comercial de uma operadora de telecomunicações B2B,
cuja prospecção ocorre no LinkedIn com apoio de ferramentas de localização de
e-mail e telefone. O SCQL centraliza o cadastro da empresa prospectada, o
decisor identificado, a origem da captura, o histórico de interações e a
evolução do lead no funil de vendas.

## Tecnologias

| Item | Descrição |
|---|---|
| Linguagem | Python 3.12 |
| Framework web | Flask 3.0.3 |
| Banco de dados | SQLite |
| Template engine | Jinja2 |
| Ambiente de execução | Replit |

## Funcionalidades

| Código | Descrição |
|---|---|
| RF01 | Cadastro da empresa prospectada, com CNPJ, segmento, porte e localidade |
| RF02 | Cadastro do lead com nome do contato, cargo, e-mail, telefone e origem |
| RF03 | Registro de interação com tipo, data, resumo e próximo passo |
| RF04 | Consulta e filtragem de leads por status, origem, consultor e período |
| RF05 | Alteração do status do lead no funil de vendas |
| RF06 | Cálculo automático do score de qualificação |
| RF07 | Relatório de captação e conversão por origem |

## Estrutura do repositório

    app.py              aplicação Flask com rotas, regras de negócio e templates
    schema.sql          script de criação das tabelas e índices
    requirements.txt    dependências do projeto
    .gitignore          arquivos ignorados pelo controle de versão

## Como executar

1. Crie um Repl com template Python.
2. Envie os arquivos `app.py`, `schema.sql` e `requirements.txt`.
3. Clique em Run. O Replit instala as dependências e inicia o servidor.
4. Abra a prévia do projeto na porta 8080.

O banco `scql.db` é criado automaticamente na primeira execução, com dados de
exemplo para demonstração das telas.

## Usuários de teste

| E-mail | Perfil | Senha |
|---|---|---|
| kariny@empresa.com.br | consultor | 123456 |
| gestor@empresa.com.br | gestor | 123456 |

## Modelo de dados

    Empresa    1:N  Lead
    Usuario    1:N  Lead
    Lead       1:N  Interacao
    Usuario    1:N  Interacao

Status possíveis do lead: Novo, Contatado, Qualificado, Proposta, Ganho,
Perdido.

## Regras de negócio implementadas

- O CNPJ precisa ter 14 dígitos e é único por empresa.
- O e-mail do contato é validado por expressão regular.
- Leads de uma empresa já cadastrada reaproveitam o registro existente.
- O score é calculado a partir do porte da empresa, do cargo do contato e da
  origem da captura, limitado a 100 pontos.
- O status é restrito pela cláusula CHECK da tabela `lead`.
- As consultas usam parâmetros vinculados, o que impede injeção de SQL.

## Autor

Kariny Kitazawa Galvão
Curso: Análise e Desenvolvimento de Sistemas
Orientador: Luis Gustavo Cardoso

2026
