# TextWeaver

TextWeaver is a FastAPI-based web server designed for working with Large Language Models (LLMs), specifically with Embeddings-style models. It simplifies the process of handling complex natural language processing tasks and offers a robust and scalable solution for both developers and researchers to store and query against embeddings in Pinecone.

## Features

- **FastAPI Integration**: Leverage the power of FastAPI for creating modern and efficient web APIs.
- **LLM and Embedding Support**: Easily work with LLMs and various embedding models for rich textual analysis.
- **Scalable Architecture**: Designed to grow with your needs, TextWeaver can be deployed across various environments.
- **User-Friendly Configuration**: Get started quickly with intuitive configuration options.

## Installation
Please note that TextWeaver requires the use of Amazon Cognito for authentication. You can find more information on how to set up Cognito [here](https://docs.aws.amazon.com/cognito/latest/developerguide/). Once you have Cognito set up, you can pass the required id tokens to the server using the `Authorization` header.

Please note that TextWeaver requires the use of SNS for sending errors and server events. You can find more information on how to set up SNS [here](https://docs.aws.amazon.com/sns/latest/dg/sns-getting-started.html). Once you have SNS set up, you will need to create a topic and pass the required topic name to the server using the `.env` file.

Please note that TextWeaver requires the use of Pinecone for storing and querying against embeddings. You can find more information on how to set up Pinecone [here](https://www.pinecone.io/docs/). Once you have Pinecone set up, you will need to create two indexes: one for the embeddings and one for the user embeddings. You can then pass the required API key and index names to the server using the `.env` file.

To install TextWeaver, you need to have a .env file in the root directory of your project. This file should contain the following variables:
```bash
HOST_IP="" # The IP to bind the server to - 0.0.0.0 for all interfaces
PORT="" # The port to bind the server to - 80 for HTTP and 443 for HTTPS
AWS_ACCESS_KEY_ID="" # The access key ID for the AWS user (recommended to use an IAM role where possible, or a user with limited permissions)
AWS_SECRET_ACCESS_KEY="" # The secret access key for the AWS user
AWS_DEFAULT_REGION="" # The default region for the AWS user
AWS_COGNITO_REGION="" # The region for the AWS Cognito user pool
AWS_USER_POOL_ID="" # The ID for the AWS Cognito user pool
AWS_USER_POOL_CLIENT_ID="" # The client ID for the AWS Cognito user pool
SNS_TOPIC_NAME="" # The name of the SNS topic to errors and server events to
PINECONE_API_KEY="" # The API key for the Pinecone environment
PINECONE_ENVIRONMENT="" # The name of the Pinecone environment
PINECONE_INDEX_NAME="" # The name of the Pinecone index
PINECONE_USER_INDEX_NAME="" # The name of the Pinecone user index
MODEL_PATH="" # Where the model path is the appropriate path for the sentence_transformer model hosted on HuggingFace
```

Install TextWeaver directly from PyPI using the following command:
```bash
pip install textweaver
```

## Usage
Once installed, you can start the TextWeaver server using the following command:

```bash
textweaver
```

For further customization and detailed documentation, please refer to the project's repository.

## Contribution

We welcome contributions from the community! Please check the contributing guidelines in the repository for more information on how you can get involved.

## License

TextWeaver is released under the MIT License. See the LICENSE file in the repository for more details.

## Contact

For any inquiries, support, or collaboration, please contact the author at wesladd@traingrc.com or open an issue on the project's GitHub page.