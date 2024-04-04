function formatarMoeda() {
        var elemento = document.getElementById('valor');
        var valor = elemento.value; 

        valor = valor + '';
        valor = parseInt(valor.replace(/[\D]+/g, ''));
        valor = valor + '';
        valor = valor.replace(/([0-9]{2})$/g, ",$1");

        if (valor.length > 6) {
            valor = valor.replace(/([0-9]{3}),([0-9]{2}$)/g, ".$1,$2");
        }

        elemento.value = valor;
        if(valor == 'NaN') elemento.value = '';

    }

function showLoading() {
    const div = document.createElement("div");
    const div2 = document.createElement("div");
    div.classList.add("loading", "centralize");
    div2.classList.add("c-loader");

    const label = document.createElement("h1");
    label.innerText = "Abastecendo o veículo ...";

    div.appendChild(div2);
    div.appendChild(label);
    //div.appendChild(div2);

    document.body.appendChild(div);
    //document.body.appendChild(div2);
}
