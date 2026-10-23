from app import create_app

app = create_app()

if __name__ == "__main__":
    # host="0.0.0.0" deixa o portal acessível pelos colegas na rede da empresa
    app.run(host="0.0.0.0", port=5000, debug=True)
