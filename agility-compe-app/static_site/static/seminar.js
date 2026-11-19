// セミナー申込フォーム（seminars/<event_id>/index.html）
// Supabase の RPC を anon キーで呼ぶだけ。申込テーブルを直接読み書きすることはない
// （RLS と権限で anon からの直接アクセスは禁止されている）。
(function () {
  "use strict";

  const form = document.getElementById("seminar-form");
  const availability = document.getElementById("availability");
  if (!form) {
    if (availability) availability.hidden = true;
    return;
  }

  const MAX_DOGS = 5;
  const eventId = Number(form.dataset.eventId);
  const baseUrl = form.dataset.supabaseUrl.replace(/\/+$/, "");
  const apiKey = form.dataset.supabaseKey;
  const dogList = document.getElementById("dog-list");
  const dogTemplate = document.getElementById("dog-template");
  const addDogButton = document.getElementById("add-dog");
  const submitButton = document.getElementById("submit-button");
  const errorBox = document.getElementById("form-error");
  const resultBox = document.getElementById("result");

  function rpc(name, body) {
    return fetch(baseUrl + "/rest/v1/rpc/" + name, {
      method: "POST",
      headers: {
        apikey: apiKey,
        Authorization: "Bearer " + apiKey,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    }).then(function (res) {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    });
  }

  function setText(el, text) {
    el.textContent = text;
  }

  // ---- 申込期間（日本時間の日付で判定。最終判定はRPC側で行う） ----
  function todayJst() {
    const d = new Date(Date.now() + 9 * 60 * 60 * 1000);
    return d.toISOString().slice(0, 10);
  }

  function formatDate(iso) {
    const p = iso.split("-");
    return Number(p[0]) + "/" + Number(p[1]) + "/" + Number(p[2]);
  }

  function periodMessage() {
    const today = todayJst();
    const opensOn = form.dataset.opensOn;
    const deadline = form.dataset.deadline;
    if (opensOn && today < opensOn) {
      return "申込受付は " + formatDate(opensOn) + " から開始します。";
    }
    if (deadline && today > deadline) {
      return "申込の受付は終了しました。";
    }
    return null;
  }

  // ---- 残り枠 ----
  function showAvailability() {
    const outOfPeriod = periodMessage();
    if (outOfPeriod) {
      availability.innerHTML = "";
      const p = document.createElement("p");
      p.className = "status-label status-caption";
      setText(p, outOfPeriod);
      availability.appendChild(p);
      form.hidden = true;
      return;
    }
    rpc("get_seminar_availability", { p_event_id: eventId })
      .then(function (a) {
        availability.innerHTML = "";
        const p = document.createElement("p");
        if (!a) {
          p.className = "status-label status-caption";
          setText(p, "このセミナーの申込情報が見つかりません。");
        } else if (!a.accepting) {
          p.className = "status-label status-caption";
          setText(p, "現在、申込を受け付けていません。");
          form.hidden = true;
        } else if (a.remaining > 0 && a.waitlist === 0) {
          p.className = "status-label status-success";
          setText(p, "受付中：定員 " + a.capacity + " 頭／残り " + a.remaining + " 頭");
        } else {
          p.className = "status-label status-info";
          setText(
            p,
            "定員に達したため、キャンセル待ちとして受け付けています（定員 " +
              a.capacity + " 頭" + (a.waitlist > 0 ? "／キャンセル待ち " + a.waitlist + " 件" : "") + "）"
          );
        }
        availability.appendChild(p);
      })
      .catch(function () {
        availability.innerHTML = "";
        const p = document.createElement("p");
        p.className = "caption";
        setText(p, "残り枠を取得できませんでした。申込はこのまま行えます。");
        availability.appendChild(p);
      });
  }

  // ---- 犬の行 ----
  function renumberDogs() {
    const rows = dogList.querySelectorAll(".dog-row");
    rows.forEach(function (row, i) {
      setText(row.querySelector(".dog-row-title"), (i + 1) + "頭目");
      row.querySelector(".remove-dog").hidden = rows.length === 1;
    });
    addDogButton.hidden = rows.length >= MAX_DOGS;
  }

  function addDog() {
    if (dogList.querySelectorAll(".dog-row").length >= MAX_DOGS) return;
    const node = dogTemplate.content.cloneNode(true);
    const row = node.querySelector(".dog-row");
    row.querySelector(".remove-dog").addEventListener("click", function () {
      row.remove();
      renumberDogs();
    });
    dogList.appendChild(node);
    renumberDogs();
  }

  addDogButton.addEventListener("click", addDog);
  addDog();

  // ---- 送信 ----
  function showError(message) {
    setText(errorBox, message);
    errorBox.hidden = false;
    errorBox.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  const FIELD_LABELS = {
    name: "氏名",
    email: "メールアドレス",
    phone: "電話番号",
    note: "備考・ご質問",
    dogs: "参加する犬の情報",
  };

  function collect() {
    const data = new FormData(form);
    const dogs = Array.prototype.map.call(dogList.querySelectorAll(".dog-row"), function (row) {
      return {
        dog_name: row.querySelector(".dog-name").value.trim(),
        breed: row.querySelector(".dog-breed").value.trim(),
        dog_class: row.querySelector(".dog-class").value,
        level: row.querySelector(".dog-level").value,
      };
    });
    return {
      p_event_id: eventId,
      p_name: String(data.get("name") || "").trim(),
      p_email: String(data.get("email") || "").trim(),
      p_phone: String(data.get("phone") || "").trim(),
      p_note: String(data.get("note") || "").trim(),
      p_dogs: dogs,
      p_website: String(data.get("website") || ""),
    };
  }

  function validate(p) {
    if (!p.p_name) return "氏名を入力してください。";
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(p.p_email)) return "メールアドレスを正しく入力してください。";
    for (let i = 0; i < p.p_dogs.length; i++) {
      const d = p.p_dogs[i];
      const n = i + 1 + "頭目";
      if (!d.dog_name) return n + "の犬の名前を入力してください。";
      if (!d.dog_class) return n + "のクラスを選択してください。";
      if (!d.level) return n + "の現在の競技レベルを選択してください。";
    }
    return null;
  }

  function showResult(res) {
    form.hidden = true;
    availability.hidden = true;
    resultBox.innerHTML = "";
    const title = document.createElement("p");
    const body = document.createElement("p");
    if (res.status === "waitlist") {
      title.className = "status-label status-info";
      setText(title, "キャンセル待ちとして受け付けました" +
        (res.waitlist_position ? "（" + res.waitlist_position + "番目）" : ""));
      setText(body, "定員に達しているため、キャンセル待ちとなります。参加いただけることになった場合は、主催者からご連絡します。");
    } else {
      title.className = "status-label status-success";
      setText(title, "お申込みを受け付けました");
      setText(body, "受付内容の確認のご連絡は、主催者から追ってお送りします。");
    }
    resultBox.appendChild(title);
    resultBox.appendChild(body);
    resultBox.hidden = false;
    resultBox.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    errorBox.hidden = true;
    const payload = collect();
    const problem = validate(payload);
    if (problem) {
      showError(problem);
      return;
    }
    submitButton.disabled = true;
    setText(submitButton, "送信中…");
    rpc("submit_seminar_application", payload)
      .then(function (res) {
        if (res && (res.status === "confirmed" || res.status === "waitlist")) {
          showResult(res);
          return;
        }
        const err = res && res.error;
        if (err === "duplicate") {
          showError("このメールアドレスでは、すでにお申込みを受け付けています。変更・取消は主催者にご連絡ください。");
        } else if (err === "not_open") {
          showError("まだ申込期間前です。申込開始日以降にお申込みください。");
        } else if (err === "closed") {
          showError("申込の受付は終了しました。");
        } else if (err === "invalid") {
          showError((FIELD_LABELS[res.field] || "入力内容") + "に誤りがあります。ご確認ください。");
        } else {
          showError("申込を受け付けられませんでした。時間をおいて再度お試しください。");
        }
      })
      .catch(function () {
        showError("通信エラーが発生しました。時間をおいて再度お試しください。");
      })
      .finally(function () {
        submitButton.disabled = false;
        setText(submitButton, "申し込む");
      });
  });

  showAvailability();
})();
